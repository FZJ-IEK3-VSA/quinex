# Docs

***quinex*** *(**qu**antitative **in**formation **ex**traction)* is a Python library and accompanying web service for extracting and analyzing quantitative information from text. It is designed to extract quantities, entities, properties and other measurement context from text. Quinex is domain-agnostic and can power a wide range of applications, such as screening of scientific literature or quantitative search.

Quinex performs **quantity span identification** and **measurement context extraction**. Quantity span identification is the task of identifying quantities in text. This task closely relates to named entity recognition and thus can be framed as sequence labeling task. Measurement context extraction is the task of identifying the measured entity, property, and other measurement context for a given quantity. Additionally, quantities are normalized to a standardized form and the quantitative statements are classified into different types (e.g., specification, goal, observation, etc.).

**Features:**
- Extract all **quantities** in a given text (optionally also imprecise quantities, e.g., “several turbines”)
- Normalize quantities to a standardized form
- Extract measurement contexts for each quantity
    - Extract the **entity** and **property** related to a quantity
    - Extract implicit properties (e.g., rated power in “the 5 MW power plant”)
    - Extract additional information (i.e., the **temporal scope, spatial scope, references, determination method, and other qualifiers**)
- Visualization of all extracted information in a dashboard
- Visualization of the extracted information directly in the text
- Experimental: Visualize citation networks to trace the original source of a quantitative statement
- Experimental: Show quantitative statements on a world map
- Experimental: Classify the type of quantitative statement (e.g., specification, goal, observation, etc.)
- Soon: Normalize entities, properties, and other contextual information to a standardized form


## Why use quinex?

Like larger, general-purpose LLMs, Quinex is built on transformer models. However, it is specifically tailored to the task of extracting quantitative information from text and thus can be much **more efficient** with orders of magnitude less model parameters. Compared to similar specialized tools, quinex is more **accurate**, provides more **contextual information**, is **domain-agnostic**, and considers **implicit properties**. Furthermore, although quinex makes mistakes determining the measurement context, it **cannot hallucinate quantities**, as they are directly extracted from the text. As quinex' predictions are grounded in the text, they are **transparent** and can be **easily verified**. Lastly, quinex is **open-source** and can be **self-hosted**.


## Limitations

* Quinex makes mistakes. Thus, the extracted information should be **verified by a human**. Quinex is not a replacement for human experts, but rather a tool to assist them in their work.
* Quinex is trained on scientific articles and Wikipedia articles and may not work well on text genres that differ significantly from the training data, such as **first-person narration or song lyrics**. 
* Quinex will not work well on **non-English texts**. The models and tokenizers are trained on English texts.
* If you need to extract quantitative information from **tables or figures**, quinex is not yet capable of doing so.
* Although quinex considers implicit properties (e.g., rated power in “the 5 MW power plant”), it cannot extract **implicit quantities** (e.g., the number of elephants and puffins in the zoo in “The zoo is very tiny hosting only an elephant and a puffin.” is one each). 
* Quinex currently does not **normalize entities, properties**, and other contextual information to a standardized form, thus "PV" and "photovoltaic" are treated as different entities and must be normalized in post-processing.
* The models for classifying the type of a quantitative statement are not yet trained on a large enough dataset and thus are not very accurate.
* The normalization of descriptions of locations to geographic coordinates is currently based on a simple and not very accurate approach.
* Parsing PDFs into machine-readable representations leads to errors. For example, mathematical formatting is often lost (e.g., 10³ to 103). This can lead to errors when normalizing the quantities.
* Overlapping quantities are currently not supported. For example, "7 (1-bit) wires per channel" would be recognized as a quantity, but not "1-bit".
* The training data does not cover a diverse set of imprecise quantifications. As a result, "a few...", "several..." are identified as quantities, but more exotic ones, such as "a truckload...",  may not.
* Due to limitations of the tokenizer, the responses of the model for the extraction of the measurement context miss special symbols such as Greek letters (e.g., λ , ε, or ∆). We will address this limitation in future releases. Quantity span identification is not affected by this.

## Citation
If you use quinex in your research, please cite the following paper:

```bibtex
@article{quinex2025,
    title = {{Quinex: Quantitative Information Extraction from Text using Open and Lightweight LLMs}},	
    author = {Göpfert, Jan and Kuckertz, Patrick and Müller, Gian and Lütz, Luna and Körner, Celine and Khuat, Hang and Stolten, Detlef and Weinand, Jann M.},
    month = okt,
    year = {2025},
}
```

The heuristic creation of training data is described in [*"Wiki-Quantities and Wiki-Measurements: Datasets of quantities and their measurement context from Wikipedia"* (2025)](https://doi.org/10.1038/s41597-025-05499-3). For a review of the field of quantitative information extraction pre-ChatGPT, see [*"Measurement Extraction with Natural Language Processing: A Review"* (2022)](https://doi.org/10.18653/v1/2022.findings-emnlp.161).


## FAQ
### How does quinex work?
Quinex uses two main components: a quantity span identification model and a measurement context extraction model. Both models are based on the transformer architecture and are fine-tuned on a large dataset tailored for their respective tasks. Quantity span identification is the task of identifying quantity spans in text. This task closely relates to named entity recognition and thus is framed as a sequence labeling task. Measurement context extraction is the task of identifying the measured entity, property and other measurement context for a given quantity. We frame this task as multi-turn generative question answering. Quantities are normalized using an efficient rule-based parser.

### How accurate is quinex?
Evaluating on the test set, quinex achieves state-of-the-art F1 scores of over 98% for identifying quantities, 82% for extracting the measured entities, and 87% for extracting the measured properties. The macro-averaged F1 over all qualifier classes is 90.47% for the large model. However, note that abstaining is often the correct answer for qualifiers. Considering alternative correct answers, the overall accuracy on the test set for quantity span identification and measurement context ectraction is 98.08% and 90.07%, respectively. End-to-end evaluation on a scientific article that is not part of the training data confirms that quantity span identification, measured entity extraction, and measured property extraction are fairly accurate with 96-97%, 78-90%, and 81-90% entity-level accuracy, respectively. For qualfiers, the accuracy is ~77% for identifying temporal scopes, 69% for spatial scopes, 89% for references, 88% for determination methods, and 56% for other not-categorized qualifiers. Note that these scores consider the extracted concepts individually and do not consider the whole quantitative statement. The entity, property, and quantity are all correctly extracted for ~79% of quantitative statements. All qualifiers are only correctly extracted for ~28% of quantitative statements.

### For which domains can I use quinex?
Quinex is domain-agnostic and can be used for many domains. However, as the training data is currently biased towards scientific texts and Wikipedia articles, other text genres (e.g., news articles, social media posts, song lyrics, etc.) may not be processed as accurately. The training data is also biased towards hydrogen technologies, Covid-19 R0 values, supercritical temperatures of superconductors, and polymer synthesis. We aim to continuously expand the training data based on user feedback and contributions. If you are interested in contributing training data, please reach out to us.

### How long does it take to analyze 1000 scientific articles?
The time it takes to analyze 1000 scientific articles depends mainly on the number of quantities in them and the compute resources used. On average, quinex requires 0.4 seconds per quantitative statement per GPU. Typically, a paper contains between 90 and 210 quantitative statements. Thus, quinex can process 1000 scientific articles in roughly 10-23 hours on a single GPU or 1-3 h on 8 GPUs. We have not yet made major efforts to optimize inference speed, so there is likely a lot of untapped potential.

### How can I contribute to quinex?
You can contribute to quinex by reporting issues, suggesting improvements, or contributing training data. The easiest way to contribute training data, is either by curate the existing training data or label new training data using the accept/reject/edit buttons when viewing annotated papers using the web interface. Note that we can only add the training data if you have the rights to modify and share the source papers.


If you have further questions or feedback, please reach out to us.