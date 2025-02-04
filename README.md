# Embedding Recycling
Preprint on ArXiv: [Embedding Recycling for Language Models](https://arxiv.org/abs/2207.04993)

## Datasets

To access our datasets for text classification, please go to the folder titled `text_classification`. 

To access our datasets for named-entity recognition (NER), please go to the folder titled `ner`. 

To access our datasets for question answering (QA), please access the TriviaQA and SQuAD datasets on HuggingFace at the following links:

- [TriviaQA](https://huggingface.co/datasets/trivia_qa)
- [SQuAD](https://huggingface.co/datasets/squad)

## Setup Environment

Run the following commands to setup a conda environment:

````
conda create --name embedding_recycling --file requirements.txt
conda activate embedding_recycling
````

## Experiment Replication

### Standard Embedding Recycling

To replicate our results for standard embedding recycling, use the conda environment listed above and run the following scripts for each dataset group:

- For text classification, use the `TextClassificationScripts/GeneralLinearClassifier_PaperResults.py` script
- For NER, use the `NER_Scripts/General_NER_Classifier_PaperResults.py` script
- For QA, use the `QA_Scripts/GeneralQuestionAnswering_PaperResults.py` script to replicate the TriviaQA results. For TriviaQA, use the `QA_Scripts/PrepareTriviaQADataset.py` for preprocessing the TriviaQA dataset using the selected model. For SQuAD, please use the "run_squad.py" script included on the [HuggingFace Transformers repository](https://github.com/huggingface/transformers/blob/main/examples/legacy/question-answering/run_squad.py), which we also include in our main directory.

The hyperparameters for replicating each experiment are included in the `HyperparameterSelection` folder. 

### Adapter-Based Embedding Recycling

To replicate our results for adapter-based embedding recycling, use the conda environment listed above and run the following scripts for each dataset group:

- For text classification, use the `TextClassificationScripts/Adapters_PaperResults.py` script
- For NER, use the `NER_Scripts/Adapters_NER_PaperResults.py` script
- For QA, use the `QA_Scripts/Adapters_QA_PaperResults.py` script to replicate the TriviaQA results. For TriviaQA, use the `QA_Scripts/PrepareTriviaQADataset.py` for preprocessing the TriviaQA dataset using the selected model. For SQuAD, please use the "run_squad.py" script included on the [HuggingFace Transformers repository](https://github.com/huggingface/transformers/blob/main/examples/legacy/question-answering/run_squad.py), which we also include in our main directory.

## Citing

````
@misc{https://doi.org/10.48550/arxiv.2207.04993,
  doi = {10.48550/ARXIV.2207.04993},
  url = {https://arxiv.org/abs/2207.04993},
  author = {Saad-Falcon, Jon and Singh, Amanpreet and Soldaini, Luca and D'Arcy, Mike and Cohan, Arman and Downey, Doug},
  keywords = {Computation and Language (cs.CL), FOS: Computer and information sciences, FOS: Computer and information sciences},
  title = {Embedding Recycling for Language Models},
  publisher = {arXiv},
  year = {2022},
  copyright = {Creative Commons Attribution 4.0 International}
}
````

`EmbeddingRecycling` is an open-source project developed by the Allen Institute for Artificial Intelligence (AI2). AI2 is a non-profit institute with the mission to contribute to humanity through high-impact AI research and engineering.
