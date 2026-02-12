# This code is partly adapted from the original implentation
# of Counts@IITK in https://github.com/akashgnr31/Counts-And-Measurement.

import sys
import numpy as np
import torch
import spacy
import transformers
from transformers import AutoTokenizer, AutoModel
import torch.nn as nn
from torchcrf import CRF
from .out_strucuture import empty_concept, empty_qualifiers_dict, empty_statement_clf_dict


class BERT_Arch(nn.Module):
    # Class adopted from original implementation at https://github.com/akashgnr31/Counts-And-Measurement
    
    def __init__(self, bert, embed_dim, hidden_dim, drop_prob, n_layers, out_dim):
    
        super(BERT_Arch, self).__init__()
        self.bert = bert 
        self.dropout = nn.Dropout(drop_prob)
        self.fc1 = nn.Linear(2*embed_dim,out_dim)
        self.w1 = nn.Linear(embed_dim, embed_dim)
        self.w2 = nn.Linear(embed_dim, embed_dim)                
        self.softmax = nn.LogSoftmax(dim = 2)
        self.crf = CRF(3, batch_first=True)  
        self.tanh = nn.Tanh()
    
    def forward(self, sent_id, mask_val, labels=None):
        x = self.bert(sent_id, attention_mask=mask_val)
        x = x.last_hidden_state
        x = self.tanh(x)
        cls = x[:,0,:]
        cls = cls.unsqueeze(1).repeat(1, 256, 1)
        cls = self.w1(cls)
        x = self.w2(x)
        x = torch.cat([x,cls], dim = 2)                
        x = self.dropout(x)
        x = self.fc1(x)
        mask_val = mask_val.type(torch.uint8)
        logit = self.softmax(x)
        if labels is not None:
            loss = -self.crf(logit, labels, mask=mask_val, reduction='mean')
            return loss
        else:
            prediction = self.crf.decode(x, mask=mask_val)
            return prediction

sys.modules['__main__'].BERT_Arch = BERT_Arch

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

try:
    tokenizer = AutoTokenizer.from_pretrained('models/scibert_local', from_pt=True)
except OSError:
    raise OSError("Download SciBERT (https://huggingface.co/allenai/scibert_scivocab_uncased/tree/main) into 'models/scibert_local')")

try:
    quantity_model = torch.load("models/scibert_base_quantity_crf_0.94.pt", weights_only=False, map_location=torch.device('cpu'))
    context_model = torch.load("models/scibert_base_measured_entity_crf_0.56.pt", weights_only=False, map_location=torch.device('cpu'))
except OSError:
    raise OSError("Download Counts@IITK model checkpoints into 'models' dir. See README of https://github.com/akashgnr31/Counts-And-Measurement for download URLs.")

delimiter = ""
delimiter_len = len(delimiter)

nlp = spacy.load("en_core_sci_sm")

def split_into_sentences(text):
    doc = nlp(text)
    sentences = []
    last_end = 0
    
    for sent in doc.sents:
        # Add any gap between sentences (whitespace, etc.)
        if sent.start_char > last_end:
            sentences.append(text[last_end:sent.start_char])
        
        # Add the sentence itself
        sentences.append(text[sent.start_char:sent.end_char])
        last_end = sent.end_char
    
    # Add any remaining text after the last sentence
    if last_end < len(text):
        sentences.append(text[last_end:])
    
    assert len("".join(sentences)) == len(text), "Sentence reconstruction failed"
    
    return sentences


def text_splitter(text):
    return split_into_sentences(text)


def extract(text, doc_offset):

    def get_spans(model, text):         

        tok_lis = tokenizer(text, return_offsets_mapping=True, add_special_tokens=False)
        sen_tok = tok_lis.input_ids

        if len(sen_tok) > 256:
            raise NotImplementedError("EXCEEDED MAX TOKEN LENGTH")

        tok_arr = np.zeros(256)
        att_mask = np.zeros(256)
        att_mask[0] = 1
        tok_arr[0] = 102
        
        for i in range(len(sen_tok)):
            tok_arr[i+1] = sen_tok[i]
            att_mask[i+1] = 1
        
        tok_arr = torch.from_numpy(tok_arr)
        att_mask = torch.from_numpy(att_mask)

        model.zero_grad()
        model.eval()
        y_pred = model(tok_arr.reshape((1,256)).long().to(device), att_mask.reshape((1,256)).long().to(device))

        # Get quantity spans from y_pred.
        spans = []
        prev_y = 0
        span = None
        for token_char_offsets, y in zip(tok_lis['offset_mapping'], y_pred[0][1:]):
            if y == 0:
                if prev_y == 0:
                    # Do nothing.
                    continue
                else:
                    # End span.
                    spans.append(span)
                    span = None
            elif y == 2 or (y == 1 and prev_y == 0):            
                if prev_y in [2, 1]:
                    # End span.
                    spans.append(span)
                    span = None
                
                # Start new span!
                span = (token_char_offsets[0], token_char_offsets[1])
            elif y == 1:
                # Extend span.
                span = (span[0], token_char_offsets[1])

            prev_y = y

        if span != None:
            # Add last span.
            spans.append(span)

        return spans

    def get_quantities(text):
        return get_spans(quantity_model, text)
        
    def get_measured_entity(text, quantity_start_char, quantity_end_char):
        highlighted_text = text[:quantity_start_char] + "$ " + text[quantity_start_char:quantity_end_char] + " $" + text[quantity_end_char:]
        spans_in_highlighted_text = get_spans(context_model, highlighted_text)
        
        if len(spans_in_highlighted_text) == 0:
            return None
        else:
            spans_in_text = []
            for (start, end) in spans_in_highlighted_text:
                
                if start > quantity_end_char:
                    start -= 4
                elif start > quantity_start_char:
                    start -= 2

                if end > quantity_end_char:
                    end -= 4
                elif end > quantity_start_char:
                    end -= 2
        
                spans_in_text.append((start, end))
            
            def get_span_distance(a, b, return_abs=False) -> int:
                """
                Get distance between two spans.
                If spans overlap, distance is negative.
                Args:
                    a (Offset): First span as (start, end).
                    b (Offset): Second span as (start, end).
                """    
                span_dist = [-1, 1][a[0] - b[1] < 0] * max(a[0] - b[1], b[0] - a[1])    
                return abs(span_dist) if return_abs else span_dist

            # From paper "[...] if our model predicts multiple entities, then we predict the one which is closest to the Quantity span."
            distances = [get_span_distance(span, (quantity_start_char, quantity_end_char)) for span in spans_in_text]
            entity_span = spans_in_text[distances.index(min(distances))]

            return entity_span
    
    qclaims = []
    if text != " ":

        quantities = get_quantities(text)
        for quantity_start_char, quantity_end_char in quantities:
            entity_offset = get_measured_entity(text, quantity_start_char, quantity_end_char)

            quantity_offsets = (quantity_start_char, quantity_end_char)
            quantity_span = text[quantity_start_char:quantity_end_char]
                        
            if entity_offset == None:
                entity = empty_concept
            else:                            
                entity_span = text[entity_offset[0]:entity_offset[1]]
                entity = {
                    "is_implicit": False,
                    "start": entity_offset[0] + doc_offset,
                    "end": entity_offset[1] + doc_offset,
                    "text": entity_span,
                    "curation": []
                }

            property = empty_concept
            
            qclaim = {
                "claim": {
                    "entity": entity,
                    "property": property,
                    "quantity": {
                        "normalized": None,
                        "is_implicit": False,
                        "start": quantity_offsets[0] + doc_offset,
                        "end": quantity_offsets[1] + doc_offset,
                        "text": quantity_span,
                        "curation": []
                    },            
                },
                "qualifiers": empty_qualifiers_dict,
                "statement_classification": empty_statement_clf_dict
            }
            
            qclaims.append(qclaim)

    return qclaims