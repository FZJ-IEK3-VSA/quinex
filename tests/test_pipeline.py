import re
import json
from pathlib import Path
from quinex import Quinex



test_str = "If you stack a gazillion giraffes, they would have a total height greater than 100 meters. The bottom giraffe would be exposed to a pressure of more than 10^5 Pa (see Figure 3)."

def test_import():
    """Test if the Quinex class can be imported and instantiated."""
    assert Quinex
    assert Quinex()


def test_pipeline():
    """Test the pipeline with different inputs.""" 
    
    quinex = Quinex(debug=False)

    # Test empty string.    
    result = quinex("")
    assert result == []

    # Test non-empty string without any quantitative claim.    
    result = quinex("This is a test string without any quantitative claim.")
    assert result == []

    # Test string with quantitative claims.
    result = quinex(test_str, skip_imprecise_quantities=True)
    assert len(result) == 2    
    assert result[0]["claim"]["quantity"]["text"] == "100 meters"
    assert result[1]["claim"]["quantity"]["text"] == "10^5 Pa"


def test_imprecise_quantities():
    """Test if the pipeline works with skip_imprecise_quantities=False."""
    quinex = Quinex()            
    result = quinex("We had a dozen of problems to discuss and presented several solutions, but a few issues remain unresolved.", skip_imprecise_quantities=False)
    assert len(result) == 3
    assert result[0]["claim"]["quantity"]["text"] == "a dozen of problems"
    assert result[1]["claim"]["quantity"]["text"] == "several solutions"
    assert result[2]["claim"]["quantity"]["text"] == "a few issues"


def test_char_offsets():
    """Test if the character offsets in the predictions are correct."""
    quinex = Quinex(empty_dict_for_empty_prediction=True)
    result = quinex(test_str, skip_imprecise_quantities=True)
    for claim in result:
        all_predictions = list(claim["claim"].values()) + list(claim["qualifiers"].values())             
        for p in all_predictions:
            if p is None:
                raise ValueError("Prediction is None.")
            elif p["start"] > p["end"]:
                raise ValueError("Character offsets are incorrect. Start should be less or equal than end.")
            elif p["start"] == 0 and p["end"] == 0 and p["text"] != "" and not p["is_implicit"]:
                raise ValueError("Character offsets for a non-empty and explicit annotation should not be (0, 0).")
            elif (p["start"] != 0 or p["end"] != 0) and (p["text"] != "" and p["is_implicit"]):
                raise ValueError("Character offsets for an implicit annotation should be (0, 0).")
            elif p["end"] != 0 and test_str[p["start"] : p["end"]] != p["text"]:
                raise ValueError("Character offsets are incorrect.")


def test_max_token_len_respected():
    """Test if the pipeline respects the maximum token length of the context model when constructing the model input."""
    
    # Get text from Wikipedia article.    
    with open(Path(__file__).parent / "test_paper.txt", "r") as f:
        long_test_str = f.read()
    
    # Make sure text is long enough.
    token_approx = len(long_test_str)/4
    assert token_approx > 5*512

    quinex = Quinex(debug=True)
    assert quinex(long_test_str)
   

def test_quantity_span_identification():
    """
    Test quantity span identification on several hard-coded examples.
    """
    quinex = Quinex(enable_statement_classification=False, enable_context_extraction=False, use_cpu=True)    
    test_strs = [
        "The process offers very high purity levels of 99.97%–99.995% according to ISO-14687:2019.",
        "The liquefaction plants can produce LH2 by cooling hydrogen to −253 °C. This process is very energy-intensive, requiring up to 40% of the hydrogen's energy content (10–15 kWh/kgLH2) [25-28].",
        "The total pipeline length increases from 26 700 km (including the GH2 pipelines with diameters over 100 mm) in the Reference (no LH2) scenario to 28 300 km in the Comprehensive (high LH2) scenario.",
        "The results in roughly 0.062 EUR/kWh el for wind turbines and 0.026 EUR/ kWh el for open-field PV.",
        "After the backmapping of clustered sequences to cDNA, the full dataset consisted of 9,858,385 cDNA sequences.",
        "In particular, a CO 2 uptake is observed when using SIFSIX-3-Cu (1.24 mmol⋅g -1 ) at 298 K adsorption temp. and 0.4 mbar partial pressure.",
        "In year 2012, 98% of the energy consumption of the sector was covered by fuels [5] , 49.7% of which was diesel, 29.5% gasoline, 14.8% aviation fuels and 1.4% liquefied petroleum and natural gas [53].",
        "The 1,754.0 Å line is well resolved compared with the rest of the multiplet, and its intensity is well constrained to be 0.25 ± 0.04 of the total intensity of the multiplet.",
        "Recent ones are more likely to be OA, as the most recent year examined contained the most OA: 44.7% of 2015 articles are OA ), 9.4% Hybrid (95% CI [8.0-10.9]), 11.3% Gold (95% CI [9.9-12.8]), and 6.3% Green (95% CI [4.9-7.8]). Well over one million OA papers were published in 2015. ",
        "Consequently, hydrogen purities of 99.96 mol% can be achieved in the standard process. Further upstream purification and recycling steps make it possible to increase the hydrogen product purity to up to 99.999 mol%.",
     ]
    quantites = []
    for test_str in test_strs:
        quantites.extend(quinex.get_quantities(test_str))
    
    groundtruth = ["99.97%–99.995%", "−253 °C", "40%", "10–15 kWh/kgLH2", "26 700 km", "100 mm", "28 300 km", "0.062 EUR/kWh el", "0.026 EUR/ kWh el", "9,858,385 cDNA sequences", "1.24 mmol⋅g -1", "298 K", "0.4 mbar", "98%", "49.7%", "29.5%", "14.8%", "1.4%", "1,754.0 Å", "0.25 ± 0.04", "44.7%", "9.4%", "95% CI [8.0-10.9]", "11.3%", "95% CI [9.9-12.8]", "6.3%", "95% CI [4.9-7.8]", "one million OA papers", "99.96 mol%", "99.999 mol%"]
    for q, gt in zip(quantites, groundtruth):
        assert q["text"] in gt


if __name__ == "__main__":    
    # test_import()
    # test_pipeline()
    # test_imprecise_quantities()
    test_char_offsets()
    test_max_token_len_respected()    
    test_quantity_span_identification()    
    print("All tests passed.")