

import torch.nn as nn
from transformers import T5Tokenizer, T5EncoderModel
from transformers import BertModel, AutoTokenizer, AutoModel, GPT2Tokenizer
#import tensorflow as tf

import pandas as pd
import numpy as np
import ast
import datasets
from datasets import load_metric
from transformers import TrainingArguments, Trainer

import pyarrow as pa
import pyarrow.dataset as ds

from torch.optim import Adam
from torch.utils.data import DataLoader
from transformers import get_scheduler

import torch
from tqdm.auto import tqdm
import statistics
import time

import subprocess as sp
import os

from sklearn.model_selection import train_test_split
import json
import random

#############################################################

random_state = 43

np.random.seed(random_state)
random.seed(random_state)
torch.manual_seed(random_state)
os.environ['PYTHONHASHSEED'] = str(random_state)

############################################################

def get_gpu_memory():
    command = "nvidia-smi --query-gpu=memory.free --format=csv"
    memory_free_info = sp.check_output(command.split()).decode('ascii').split('\n')[:-1][1:]
    memory_free_values = [int(x.split()[0]) for i, x in enumerate(memory_free_info)]
    return memory_free_values

############################################################

class CustomBERTModel(nn.Module):
    def __init__(self, number_of_labels, model_choice, dropout_layer, frozen, 
                 frozen_layer_count, average_hidden_state, frozen_embeddings):

          super(CustomBERTModel, self).__init__()
          
          if model_choice == "roberta-large":

            model_encoding = AutoModel.from_pretrained(model_choice)
            embedding_size = 1024
            self.encoderModel = model_encoding

          elif model_choice == "nreimers/MiniLMv2-L6-H384-distilled-from-RoBERTa-Large":

            model_encoding = AutoModel.from_pretrained(model_choice)
            embedding_size = 384
            self.encoderModel = model_encoding

          elif model_choice == "microsoft/deberta-v2-xlarge":

            model_encoding = AutoModel.from_pretrained(model_choice)
            embedding_size = 1536
            self.encoderModel = model_encoding

          else:

            model_encoding = AutoModel.from_pretrained(model_choice)
            embedding_size = 768
            self.encoderModel = model_encoding



          if frozen == True:
            print("Freezing the model parameters")
            for param in self.encoderModel.parameters():
                param.requires_grad = False



          if frozen_layer_count > 0:

            if model_choice == "t5-3b":

                print("Freezing T5-3b")
                print("Number of Layers: " + str(len(self.encoderModel.encoder.block)))

                for parameter in self.encoderModel.parameters():
                    parameter.requires_grad = False

                for i, m in enumerate(self.encoderModel.encoder.block):        
                    #Only un-freeze the last n transformer blocks
                    if i+1 > 24 - frozen_layer_count:
                        print(str(i) + " Layer")
                        for parameter in m.parameters():
                            parameter.requires_grad = True

            elif model_choice == "distilbert-base-uncased":

                #print(self.encoderModel.__dict__)
                print("Number of Layers: " + str(len(list(self.encoderModel.transformer.layer))))

                layers_to_freeze = self.encoderModel.transformer.layer[:frozen_layer_count]
                for module in layers_to_freeze:
                    for param in module.parameters():
                        param.requires_grad = False

            else:

                print("Number of Layers: " + str(len(list(self.encoderModel.encoder.layer))))

                layers_to_freeze = self.encoderModel.encoder.layer[:frozen_layer_count]
                for module in layers_to_freeze:
                    for param in module.parameters():
                        param.requires_grad = False



          
          if frozen_embeddings == True:
            print("Frozen Embeddings Layer")
            for param in self.encoderModel.embeddings.parameters():
                param.requires_grad = False





          ### New layers:
          self.linear1 = nn.Linear(embedding_size, 256)
          self.linear2 = nn.Linear(256, number_of_labels)

          self.embedding_size = embedding_size
          self.average_hidden_state = average_hidden_state


          

    def forward(self, ids, mask):
          
          total_output = self.encoderModel(ids, 
                   						   attention_mask=mask)

          sequence_output = total_output['last_hidden_state']

          linear1_output = self.linear1(sequence_output[:,0,:].view(-1, self.embedding_size))
          linear2_output = self.linear2(linear1_output)

          return linear2_output



############################################################

device = "cuda:0"
device = torch.device(device)

num_epochs = 100 #1000 #10
patience_value = 10 #10 #3
current_dropout = True
number_of_runs = 10 #1 #5
frozen_choice = False
average_hidden_state = False

validation_set_scoring = False

assigned_batch_size = 4
gradient_accumulation_multiplier = 8







############################################################
# Select model and hyperparameters here
############################################################

classification_datasets = ['chemprot', 'sci-cite', "sciie-relation-extraction"]
learning_rate_for_each_dataset = [1e-5, 1e-5, 1e-5] # Learning rate choices for the Chemprot, SciCite, 
                                                    # and SciERC-Relation respectively

frozen_layers = 0 # For freezing k-later layers of transformer model
frozen_embeddings = False # For freezing input embeddings layer of transformer model

model_choice = "microsoft/deberta-v2-xlarge"
#model_choice = 'roberta-large'
#model_choice = 'allenai/scibert_scivocab_uncased'
#model_choice = 'nreimers/MiniLMv2-L6-H384-distilled-from-RoBERTa-Large'
#model_choice = 'nreimers/MiniLMv2-L6-H768-distilled-from-RoBERTa-Large'
#model_choice = "distilbert-base-uncased"

############################################################







############################################################

tokenizer = AutoTokenizer.from_pretrained(model_choice, model_max_length=512)

def tokenize_function(examples):

    return tokenizer(examples["text"], padding="max_length", truncation=True)#.input_ids

############################################################

best_checkpoints_folder = "best_checkpoints/"
if not os.path.isdir(best_checkpoints_folder):

    print("Creating folder: " + best_checkpoints_folder)
    os.mkdir(best_checkpoints_folder)

try:
	os.mkdir(best_checkpoints_folder + model_choice.replace("/", "-"))
except:
	print("Already exists")
	print(best_checkpoints_folder + model_choice.replace("/", "-"))

for dataset in classification_datasets:
    try:
        os.mkdir(best_checkpoints_folder + "/" + dataset)
    except:
        print("Already exists")
        print(best_checkpoints_folder + "/" + dataset)

############################################################

dataset_folder_path = "paper_results_text_classification/"

if not os.path.isdir(dataset_folder_path):

	print("Creating folder: " + dataset_folder_path)
	os.mkdir(dataset_folder_path)

dataset_folder_path += model_choice.replace("/", "-") + "/"

if not os.path.isdir(dataset_folder_path):

    print("Creating folder: " + dataset_folder_path)
    os.mkdir(dataset_folder_path)

for dataset in classification_datasets:
    try:
        print("Making: " + dataset_folder_path + dataset)
        os.mkdir(dataset_folder_path + dataset)
    except:
        print("Already exists")
        print(dataset_folder_path + dataset)

############################################################

learning_rate_to_results_dict = {}

for chosen_learning_rate, dataset in zip(learning_rate_for_each_dataset, classification_datasets):

        best_model_save_path = "best_checkpoints/" + model_choice.replace("/","-") + "/"
        best_model_save_path += "Dataset_" + dataset + "_"
        best_model_save_path += "chosen_learning_rate_" + str(chosen_learning_rate) + "_"
        best_model_save_path += "frozen_layers_" + str(frozen_layers) + "_"
        best_model_save_path += "frozen_embeddings_" + str(frozen_embeddings) + "_"
        best_model_save_path += "num_epochs_" + str(num_epochs) + "_"
        best_model_save_path += "patience_value_" + str(patience_value) + "_"
        best_model_save_path += "number_of_runs_" + str(number_of_runs) + "_"


        ############################################################


        print("--------------------------------------------------------------------------")
        print("Starting new learning rate: " + str(chosen_learning_rate))
        print("For dataset: " + dataset)
        print("--------------------------------------------------------------------------")

        print("GPU Memory available at the start")
        print(get_gpu_memory())

        execution_start = time.time()

        print("Dataset: " + dataset)
        print("Model: " + model_choice)
        print("Dropout: " + str(current_dropout))
        print("Frozen Choice: " + str(frozen_choice))
        print("Number of Runs: " + str(number_of_runs))
        print('Learning Rate: ' + str(chosen_learning_rate))
        print("Number of Frozen Layers: " + str(frozen_layers))
        print("Frozen Embeddings: " + str(frozen_embeddings))
        print("Patience: " + str(patience_value))
        print("Average Hidden Layers: " + str(average_hidden_state))
        print("Validation Set Choice: " + str(validation_set_scoring))
        print("Number of Epochs: " + str(num_epochs))

        # Chemprot train, dev, and test
        with open('text_classification/' + dataset + '/train.txt') as f:

            train_set = f.readlines()
            train_set = [ast.literal_eval(line) for line in train_set]
            train_set_text = [line['text'] for line in train_set]
            train_set_label = [line['label'] for line in train_set]

        with open('text_classification/' + dataset + '/dev.txt') as f:
            
            dev_set = f.readlines()
            dev_set = [ast.literal_eval(line) for line in dev_set]

            dev_set_text = []
            dev_set_label = []
            for line in dev_set:

                # Fix bug in MAG dev where there is a single label called "category"
                if line['label'] != 'category':
                    dev_set_text.append(line['text'])
                    dev_set_label.append(line['label'])
                else:
                    print("Found the error with category")

        with open('text_classification/' + dataset + '/test.txt') as f:
            
            test_set = f.readlines()
            test_set = [ast.literal_eval(line) for line in test_set]
            test_set_text = [line['text'] for line in test_set]
            test_set_label = [line['label'] for line in test_set]


        ############################################################

        labels_list = sorted(list(set(train_set_label)))

        label_to_value_dict = {}

        count = 0
        for label in labels_list:
          label_to_value_dict[label] = count
          count += 1

        train_set_label = [label_to_value_dict[label] for label in train_set_label]
        dev_set_label = [label_to_value_dict[label] for label in dev_set_label]
        test_set_label = [label_to_value_dict[label] for label in test_set_label]

        ############################################################

        if validation_set_scoring == True:

            training_dataset_pandas = pd.DataFrame({'label': train_set_label, 'text': train_set_text})#[:1000]
            training_dataset_arrow = pa.Table.from_pandas(training_dataset_pandas)
            training_dataset_arrow = datasets.Dataset(training_dataset_arrow)

            validation_dataset_pandas = pd.DataFrame({'label': dev_set_label, 'text': dev_set_text})#[:1000]
            validation_dataset_arrow = pa.Table.from_pandas(validation_dataset_pandas)
            validation_dataset_arrow = datasets.Dataset(validation_dataset_arrow)

            test_dataset_pandas = pd.DataFrame({'label': dev_set_label, 'text': dev_set_text})
            test_dataset_arrow = pa.Table.from_pandas(test_dataset_pandas)
            test_dataset_arrow = datasets.Dataset(test_dataset_arrow)

        else:

            training_dataset_pandas = pd.DataFrame({'label': train_set_label, 'text': train_set_text})#[:1000]
            training_dataset_arrow = pa.Table.from_pandas(training_dataset_pandas)
            training_dataset_arrow = datasets.Dataset(training_dataset_arrow)

            validation_dataset_pandas = pd.DataFrame({'label': dev_set_label, 'text': dev_set_text})#[:1000]
            validation_dataset_arrow = pa.Table.from_pandas(validation_dataset_pandas)
            validation_dataset_arrow = datasets.Dataset(validation_dataset_arrow)

            test_dataset_pandas = pd.DataFrame({'label': test_set_label, 'text': test_set_text})
            test_dataset_arrow = pa.Table.from_pandas(test_dataset_pandas)
            test_dataset_arrow = datasets.Dataset(test_dataset_arrow)


        ############################################################


        classification_dataset = datasets.DatasetDict({'train' : training_dataset_arrow, 
                                        'validation': validation_dataset_arrow, 
                                        'test' : test_dataset_arrow})
        tokenized_datasets = classification_dataset.map(tokenize_function, batched=True)


        tokenized_datasets = tokenized_datasets.remove_columns(["text"])
        tokenized_datasets = tokenized_datasets.rename_column("label", "labels")
        tokenized_datasets.set_format("torch")


        ############################################################

        lowest_recorded_validation_loss = 10000

        macro_f1_scores = []
        micro_f1_scores = []

        for i in range(0, number_of_runs):

            checkpoint_path = "paper_results_text_classification/" + model_choice.replace("/", "-") + "/" + dataset + "/" + str(chosen_learning_rate) + "_"
            checkpoint_path += str(frozen_layers) + "_" + str(frozen_embeddings) + "_" + str(number_of_runs)
            checkpoint_path += str(validation_set_scoring) + "_Run_" + str(i) + ".pt"

            run_start = time.time()

            print("Loading Model")
            print("Checkpoint: " + checkpoint_path)

            train_dataloader = DataLoader(tokenized_datasets['train'], batch_size=assigned_batch_size)
            validation_dataloader = DataLoader(tokenized_datasets['validation'], batch_size=assigned_batch_size)
            eval_dataloader = DataLoader(tokenized_datasets['test'], batch_size=assigned_batch_size)

            print("Number of labels: " + str(len(set(train_set_label))))

            ############################################################

            model = CustomBERTModel(len(set(train_set_label)), model_choice, current_dropout, 
                                    frozen_choice, frozen_layers, average_hidden_state, frozen_embeddings)

            model.to(device)

            ############################################################


            #optimizer = AdamW(model.parameters(), lr=5e-5)

            criterion = nn.CrossEntropyLoss()
            optimizer = Adam(model.parameters(), lr=chosen_learning_rate) #5e-6
            #optimizer = Adam(model.parameters(), lr=1e-5) #5e-6

            num_training_steps = num_epochs * len(train_dataloader)

            lr_scheduler = get_scheduler(
                name="linear", optimizer=optimizer, num_warmup_steps=100, num_training_steps=num_training_steps
            )

            ############################################################



            # to track the training loss as the model trains
            train_losses = []
            # to track the validation loss as the model trains
            valid_losses = []
            # to track the average training loss per epoch as the model trains
            avg_train_losses = []
            # to track the average validation loss per epoch as the model trains
            avg_valid_losses = []


            # import EarlyStopping
            from pytorchtools import EarlyStopping
            # initialize the early_stopping object
            early_stopping = EarlyStopping(patience=patience_value, verbose=True, path=checkpoint_path)
            #early_stopping = EarlyStopping(patience=10, verbose=True)

            print("Checkpoint Path: " + checkpoint_path)


            print("Beginning Training")

            total_epochs_performed = 0

            for epoch in range(num_epochs):

                total_epochs_performed += 1

                print("Current Epoch: " + str(epoch))

                progress_bar = tqdm(range(len(train_dataloader)))


                gradient_accumulation_count = 0

                model.train()
                for batch in train_dataloader:

                    #with torch.no_grad():
                    
                        batch = {k: v.to(device) for k, v in batch.items()}
                        labels = batch['labels']

                        new_batch = {'ids': batch['input_ids'].to(device), 'mask': batch['attention_mask'].to(device)}
                        outputs = model(**new_batch)

                        loss = criterion(outputs, labels)

                        loss.backward()

                        gradient_accumulation_count += 1
                        if gradient_accumulation_count % (gradient_accumulation_multiplier) == 0:
                        	optimizer.step()
                        	lr_scheduler.step()
                        	optimizer.zero_grad()
                        
                        progress_bar.update(1)
                        train_losses.append(loss.item())


                progress_bar = tqdm(range(len(validation_dataloader)))

                model.eval()
                for batch in validation_dataloader:

                    #with torch.no_grad():
                    
                        batch = {k: v.to(device) for k, v in batch.items()}
                        labels = batch['labels']

                        new_batch = {'ids': batch['input_ids'].to(device), 'mask': batch['attention_mask'].to(device)}
                        outputs = model(**new_batch)

                        loss = criterion(outputs, labels)
                        progress_bar.update(1)

                        valid_losses.append(loss.item())


                # print training/validation statistics 
                # calculate average loss over an epoch
                train_loss = np.average(train_losses)
                valid_loss = np.average(valid_losses)
                avg_train_losses.append(train_loss)
                avg_valid_losses.append(valid_loss)
                
                epoch_len = len(str(num_epochs))
                
                print_msg = (f'[{epoch:>{epoch_len}}/{num_epochs:>{epoch_len}}] ' +
                             f'train_loss: {train_loss:.5f} ' +
                             f'valid_loss: {valid_loss:.5f}')
                
                print(print_msg)
                
                # clear lists to track next epoch
                train_losses = []
                valid_losses = []
                
                # early_stopping needs the validation loss to check if it has decresed, 
                # and if it has, it will make a checkpoint of the current model
                early_stopping(valid_loss, model)

                if valid_loss < lowest_recorded_validation_loss:
                	lowest_recorded_validation_loss = valid_loss
           	    	torch.save(model.state_dict(), best_model_save_path)
                
                if early_stopping.early_stop:
                    print("Early stopping")
                    break





            ############################################################

            print("Loading the Best Model")

            model.load_state_dict(torch.load(checkpoint_path))

            ############################################################

            print("Beginning Evaluation")

            metric = load_metric("accuracy")

            total_predictions = torch.FloatTensor([]).to(device)
            total_references = torch.FloatTensor([]).to(device)

            progress_bar = tqdm(range(len(eval_dataloader)))
            for batch in eval_dataloader:

                with torch.no_grad():

                    batch = {k: v.to(device) for k, v in batch.items()}
                    labels = batch['labels']

                    new_batch = {'ids': batch['input_ids'].to(device), 'mask': batch['attention_mask'].to(device)}

                    outputs = model(**new_batch)

                    logits = outputs
                    predictions = torch.argmax(logits, dim=-1)
                    metric.add_batch(predictions=predictions, references=labels)

                    total_predictions = torch.cat((total_predictions, predictions), 0)
                    total_references = torch.cat((total_references, labels), 0)

                    progress_bar.update(1)


	        ############################################################

            print("-----------------------------------------------------------------")

            results = metric.compute(references=total_predictions, predictions=total_references)
            print("Accuracy for Test Set: " + str(results['accuracy']))

            f_1_metric = load_metric("f1")
            macro_f_1_results = f_1_metric.compute(average='macro', references=total_predictions, predictions=total_references)
            print("Macro F1 for Test Set: " + str(macro_f_1_results['f1'] * 100))
            micro_f_1_results = f_1_metric.compute(average='micro', references=total_predictions, predictions=total_references)
            print("Micro F1 for Test Set: " + str(micro_f_1_results['f1']  * 100))

            macro_f1_scores.append(macro_f_1_results['f1'] * 100)
            micro_f1_scores.append(micro_f_1_results['f1']  * 100)

            print("GPU Memory available at the end")
            print(get_gpu_memory())
            print("-----------------------------------------------------------------")

            ############################################################

        print("-----------------------------------------------------------------")
        print("Final Results for Spreadsheet")
        print("-----------------------------------------------------------------")
        print("Dataset: " + dataset)
        print("Model: " + model_choice)
        print("Number of Runs: " + str(number_of_runs))
        print("Number of Epochs: " + str(num_epochs))
        print("Patience: " + str(patience_value))
        print("Number of Frozen Layers: " + str(frozen_layers))
        print("Frozen Embeddings: " + str(frozen_embeddings))
        print("Validation Set Choice: " + str(validation_set_scoring))
        print("-----------------------------------------------------------------")

        print("Micro and Macro F1 Scores")
        print(str(round(statistics.mean(micro_f1_scores), 2)))
        print(str(round(statistics.mean(macro_f1_scores), 2)))
        print("-----------------------------------------------------------------")
        
        print("Micro and Macro F1 Standard Deviations")
        print(str(round(statistics.stdev(micro_f1_scores), 2)))
        print(str(round(statistics.stdev(macro_f1_scores), 2)))

        print("-----------------------------------------------------------------")

