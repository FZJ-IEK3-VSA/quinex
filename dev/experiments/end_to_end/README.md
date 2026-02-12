# Code for manual evaluation on papers

This is the code that was used for evaluating quinex against CQE, grobid-quantities, and Counts@IITK in quantity span identification and measurement context extraction. The paper's PDFs were parsed using Grobid. Please note that statement type classification and quantity normalization are not evaluated. Quantity normalization was performed using an older version of quinex-utils.

Steps:
1. Run quinex on papers
2. Run CQE, grobid-quantities, and Counts@IITK on papers with `01_run_end_to_end_comparison.py`
3. Use the paper GUI to manually curate the model predictions
4. Evaluate human judgements `02_evaluate_end_to_end_judgements.py`