import semchunk
from time import time
from text_processing_utils.highlight_context import enclose_with_special_symbol
from quinex.extract.utils.transformers import load_transformers_pipe, get_text_chunking_helper
from quinex import msg


class StatementTypeClassification:
    """
    Classify the type, rational, and system of quantity statements with
    multi-label text classification using an encoder-only transformer model.

    **Type** refers to the kind of claim made. The available classes are:
     - "observation"
     - "assumption"
     - "prediction"
     - "requirement"
     - "specification"
     - "goal"
     - "feasibility estimation"

    **Rational** refers to how the value was obtained. The available classes are:    
     - "experiments"
     - "simulation or calculation"
     - "regression"
     - "expert elicitation"
     - "literature review"
     - "individual literature sources"
     - "company reported"               
     - "rough estimate or analogy"
     - "arbitrary"

    **System** refers to the kind of system the claim is about. The available classes are:
     - "real world"
     - "lab or prototype or pilot system"
     - "model"
     
    """
    
    def __init__(self, model_path, clf_quantity_enclosing=("🍏", "🍏"), devices=["cpu"], batch_size=8, dtype="auto", verbose=False, debug=False): 
            
        self.verbose = verbose
        self.debug = debug
        self.token_counter, self.chunk_size = get_text_chunking_helper(model_path, task="text-classification")
        self.clf_quantity_enclosing = clf_quantity_enclosing

        # Load parallel statement classification pipelines.
        self.statement_clf_pipelines = [load_transformers_pipe("text-classification", model_path, device, batch_size=batch_size, dtype=dtype, verbose=verbose) for device in devices]


    def __call__(self, quantity_batch, device_rank, text, semantic_boundaries, add_curation_fields=False):       
            
            start = time()

            quantities = quantity_batch

            # ====================================
            #   Perform statement classification
            # ====================================
            statement_clf_inputs = []
            for quantity in quantities:            
                
                try:    
                    quantity_offset = (quantity["start"], quantity["end"])
                    statement_clf_context, _ = enclose_with_special_symbol(
                        text,
                        quantity_offset,
                        start_symbol=self.clf_quantity_enclosing[0],
                        end_symbol=self.clf_quantity_enclosing[1],        
                    )

                except Exception as e:
                    print("Quantity that caused error:", quantity)
                    raise print(f"Error in statement classification: {e}")
                                
                # Take chunk size smaller than the maximum model input size as the training examples were fairly small.                
                chunk_size = 200 # TODO: Change chunk size with new training data.                
                
                centering_span = (quantity_offset[0], quantity_offset[1]+len(self.clf_quantity_enclosing[0])+len(self.clf_quantity_enclosing[1]))
                # _, statement_clf_context = semchunk.get_single_centered_chunk(statement_clf_context, centering_char_offsets=centering_span, chunk_size=chunk_size, semantic_boundaries=semantic_boundaries,token_counter=self.token_counter)
                statement_clf_context = semchunk.get_single_centered_chunk(statement_clf_context, centering_char_offsets=centering_span, chunk_size=chunk_size, token_counter=self.token_counter, semantic_boundaries=semantic_boundaries, offsets=False)

                statement_clf_inputs.append(statement_clf_context)

            clf_predictions = self.statement_clf_pipelines[device_rank](statement_clf_inputs)
            
            statement_clfs = []
            for q, clf in zip(quantities, clf_predictions):
                statement_clfs.append({
                    "quantity": q,
                    "statement_classification": self._postprocess_statement_clf_prediction(clf, add_curation_fields=add_curation_fields)
                })

            if self.verbose:
                msg.good("Statement classification done in", round(time()-start, 3), "s.")

            return statement_clfs


    def _postprocess_statement_clf_prediction(self, clf_prediction: list[dict], abstain_label=None, relative_thr: float=0.1, absolute_thr: float=0.2, add_curation_fields=True):
        """
        Postprocess statement classification predictions.

        The type class referes to the kind of claim made, the ration class refers to how the value was obtained, 
        and the system class refers to the kind of system the claim is about. See the labels per class below.

        Args:
            clf_prediction: List of dictionaries containing the prediction for each class.
            abstain_label: Label to return if no class is chosen.
            relative_thr: Percentage the score must be higher than the second best score to be considered.
            absolute_thr: Score must be above this threshold to be considered.

        """
        
        # What kind of claim is being made?
        STATEMENT_TYPE_CLASSES = ["assumption", "feasibility_estimation", "goal", "observation", "prediction", "requirement", "specification"]
        
        # How was the value obtained?
        STATEMENT_RATIONAL_CLASSES = ["arbitrary", "company_reported", "experiments", "expert_elicitation", "individual_literature_sources", 
        "literature_review", "regression", "simulation_or_calculation", "rough_estimate_or_analogy"]

        # And what kind of system is it about?
        STATEMENT_SYSTEM_CLASSES = ["real_world", "lab_or_prototype_or_pilot_system", "model"]            
            
        # Get groups.
        statement_type_scores = []
        statement_rational_scores = []
        statement_system_scores = []
        statement_type_labels = []
        statement_rational_labels = []
        statement_system_labels = []
        for p in clf_prediction:
            if p["label"] in STATEMENT_TYPE_CLASSES:                    
                statement_type_labels.append(p["label"])
                statement_type_scores.append(p["score"])
            elif p["label"] in STATEMENT_RATIONAL_CLASSES:                    
                statement_rational_labels.append(p["label"])
                statement_rational_scores.append(p["score"])
            elif p["label"] in STATEMENT_SYSTEM_CLASSES:                    
                statement_system_labels.append(p["label"])
                statement_system_scores.append(p["score"])
            else:
                raise ValueError(f"Unknown class. {p['label']}")
            
        statement_type = self._get_most_likely_class(statement_type_scores, statement_type_labels, abstain_label=abstain_label, relative_thr=relative_thr, absolute_thr=absolute_thr)
        statement_rational = self._get_most_likely_class(statement_rational_scores, statement_rational_labels, abstain_label=abstain_label, relative_thr=relative_thr, absolute_thr=absolute_thr)
        statement_system = self._get_most_likely_class(statement_system_scores, statement_system_labels, abstain_label=abstain_label, relative_thr=relative_thr, absolute_thr=absolute_thr)

        if add_curation_fields:
            classification_result = {
                "type": {"class": statement_type, "curation": []},
                "rational": {"class": statement_rational, "curation": []},
                "system": {"class": statement_system, "curation": []}
            }
        else:
            classification_result = {
                "type": statement_type,
                "rational": statement_rational,
                "system": statement_system
            }

        return classification_result
    

    def _get_most_likely_class(self, scores: list[float], labels: list[str], abstain_label=None, relative_thr: float=0.1, absolute_thr: float=0.2):
        """
        Get the most likely class. If no class is likely or multiple classes are roughly equally likely, take none.
        
        Args:
            scores: List of scores. Each score corresponds to a label and is between 0 and 1.
            labels: List of labels. Order corresponds to the order of the scores.
            abstain_label: Label to return if no class is chosen.
            relative_thr: Percentage the score must be higher than the second best score to be considered.
            absolute_thr: Score must be above this threshold to be considered.
        """
        max_score = max(scores)
        max_score_idx = scores.index(max_score)
        other_scores_thr = max_score/(1+relative_thr)
        if max_score > absolute_thr \
            and not any(score > other_scores_thr for score in scores[:max_score_idx] + scores[max_score_idx+1:]):
            return labels[max_score_idx]
        else:
            return abstain_label        