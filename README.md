
<a href="https://www.fz-juelich.de/en/ice/ice-2"><img src="https://github.com/FZJ-IEK3-VSA/README_assets/blob/main/JSA-Header.svg?raw=True" alt="Forschungszentrum Juelich Logo" height="70px"></a>

<img src="assets/quinex_logo.svg" height="120" />

# Quinex

***quinex*** *(**qu**antitative **in**formation **ex**traction)* is a Python library for extracting and analyzing quantitative information from text. It is designed to extract quantities, entities, properties and other measurement context from text. Quinex is domain-agnostic and can power a wide range of applications, such as screening of scientific literature or quantitative search.

Quinex performs **quantity span identification** and **measurement context extraction**. Quantity span identification is the task of identifying quantities in text. This task closely relates to named entity recognition and thus can be framed as sequence labeling task. Measurement context extraction is the task of identifying the measured entity, property, and other measurement context for a given quantity. Additionally, quantities are normalized to a standardized form and the quantitative statements are classified into different types (e.g., specification, goal, observation, etc.).

### Features
- Extract all **quantities** in a given text (optionally also imprecise quantities, e.g., “several turbines”)
- Normalize quantities to a standardized form
- Extract measurement contexts for each quantity
    - Extract the **entity** and **property** related to a quantity
    - Extract implicit properties (e.g., rated power in “the 5 MW power plant”)
    - Extract additional information (i.e., the **temporal scope, spatial scope, references, determination method, and other qualifiers**)
- Experimental: Classify the type of quantitative statement (e.g., specification, goal, observation, etc.)

Furthermore, Quinex includes an experimental web service that shows extracted information on a dashboard as well as directly in the source text. From there, the information can be curated. Visualizations include world maps, timelines, and citation networks for tracing the original source of a quantitative statement.


### Related resources
- [Models](https://huggingface.co/collections/JuelichSystemsAnalysis/quinex-v0)
- [Datasets](https://github.com/FZJ-IEK3-VSA/quinex-datasets)
- [quinex-utils](https://github.com/FZJ-IEK3-VSA/quinex-utils)

### Related publications

Quinex is described in detail in the following article: 
*"Quinex: Quantitative Information Extraction from Text using Open and Lightweight LLMs"* (published soon). Furthermore, the heuristic creation of training data is described in [*"Wiki-Quantities and Wiki-Measurements: Datasets of quantities and their measurement context from Wikipedia"* (2025)](https://doi.org/10.1038/s41597-025-05499-3). For a review of the field of quantitative information extraction pre-ChatGPT, see [*"Measurement Extraction with Natural Language Processing: A Review"* (2022)](https://doi.org/10.18653/v1/2022.findings-emnlp.161).


## Why use quinex?

Like larger, general-purpose LLMs, Quinex is built on transformer models. However, it is specifically tailored to the task of extracting quantitative information from text and thus can be much **more efficient** with orders of magnitude less model parameters. Compared to similar specialized tools, quinex is more **accurate**, provides more **contextual information**, is **domain-agnostic**, and considers **implicit properties**. Furthermore, although quinex does occasionally misinterpret the measurement context, it **cannot hallucinate quantities**, as they are extracted directly from the text. As quinex' predictions are grounded in the text, they are **transparent** and can be **easily verified**. Lastly, quinex is **open-source** and can be **self-hosted**.


## Getting started

First, familiarize yourself with the [strengths](#why-use-quinex) and [limitations](#limitations) of quinex. You may also want to read the [FAQ](#faq) section.

Quinex can be used as a **Python library**, via **API**, or in a **web service** to for analyzing scientific literature. See the [usage guide](./docs/01_usage_guide.md) for detailed instructions.
To use quinex as a **Python library** create a virtual environment (for example, via mamba) and activate it:
```bash
mamba create --name "quinex_env" python=3.9 -c conda-forge
mamba activate quinex_env
```
Then, install quinex via pip:
```bash
pip install git+https://github.com/FZJ-IEK3-VSA/quinex.git
python3 -m spacy download en_core_web_md
```

Then, you can use quinex as follows:
```python
>>> from quinex import Quinex

>>> quinex = Quinex()
>>> text = "Reykjanesvirkjun is a geothermal power station located in Iceland with a power output of 130 MW."

>>> qclaims = quinex(text)
[
    {
        'claim': {
            'entity': {
                'is_implicit': False,
                'start': 0,
                'end': 16,
                'text': 'Reykjanesvirkjun'
            }, 
            'property': {
                'is_implicit': False,
                'start': 73,
                'end': 85,
                'text': 'power output'
            }, 
            'quantity': {
                'is_implicit': False,
                'start': 89,
                'end': 95,
                'text': '130 MW',
                'normalized': { [...] 'numeric_value': 130 [...] 'unit': [...] 'text': 'MW', 'exponent': 1, 'uri':'http://qudt.org/vocab/unit/MegaW' [...] }
        'qualifiers': {
            'temporal_scope': None
            'spatial_scope': {
                'text': 'Iceland',            
                'start': 58,
                'end': 65,
                'is_implicit': False
            }, 
            'reference': None
            'method': None
            'qualifier': None
        }, 
        'statement_classification': {
            'type': 'observation',
            'rational': 'arbitrary',
            'system': 'real_world'
        }
    }
]
```
For more examples, see the [usage guide](./docs/01_usage_guide.md) and the [examples](./examples).

## Limitations

> [!IMPORTANT]
> Quinex makes mistakes. Thus, the extracted information should be **verified by humans**.

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
You can contribute to quinex by reporting issues, suggesting improvements, or contributing training data. Note that we can only add the training data if you have the rights to modify and share the source texts.

If you have further questions or feedback, please reach out to us.


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


## License

For the most part, Quinex is licensed under the MIT License. However, there are some exceptions. Please see the [LICENSE](./LICENSE.md) file for details.


## About Us 

<a href="https://www.fz-juelich.de/en/ice/ice-2"><img src="https://github.com/FZJ-IEK3-VSA/README_assets/blob/main/iek3-square.png?raw=True" alt="Institute image ICE-2" width="280" align="right" style="margin:0px 10px"/></a>

We are the <a href="https://www.fz-juelich.de/en/ice/ice-2">Institute of Climate and Energy Systems (ICE) - Jülich Systems Analysis</a> belonging to the <a href="https://www.fz-juelich.de/en">Forschungszentrum Jülich</a>. Our interdisciplinary department's research is focusing on energy-related process and systems analyses. Data searches and system simulations are used to determine energy and mass balances, as well as to evaluate performance, emissions and costs of energy systems. The results are used for performing comparative assessment studies between the various systems. Our current priorities include the development of energy strategies, in accordance with the German Federal Government’s greenhouse gas reduction targets, by designing new infrastructures for sustainable and secure energy supply chains and by conducting cost analysis studies for integrating new technologies into future energy market frameworks.


## Acknowledgements

The authors would like to thank the German Federal Government, the German state governments, and the Joint Science Conference (GWK) for their funding and support as part of the NFDI4Ing consortium. Funded by the German Research Foundation (DFG) – project number: 442146713. Furthermore, this work was supported by the Helmholtz Association under the program "Energy System Design".

<p float="left">
    <a href="https://nfdi4ing.de/"><img src="https://nfdi4ing.de/wp-content/uploads/2018/09/logo.svg" alt="NFDI4Ing Logo" width="130px"></a>&emsp;<a href="https://www.helmholtz.de/en/"><img src="https://www.helmholtz.de/fileadmin/user_upload/05_aktuelles/Marke_Design/logos/HG_LOGO_S_ENG_RGB.jpg" alt="Helmholtz Logo" width="200px"></a>
</p>