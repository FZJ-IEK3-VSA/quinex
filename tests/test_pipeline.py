from pathlib import Path

import pytest
from quinex import Quinex



TEST_STR = "If you stack a gazillion giraffes, they would have a total height greater than 100 meters. The bottom giraffe would be exposed to a pressure of more than 10^5 Pa (see Figure 3)."


def test_import():
    """Quinex class is importable."""
    assert Quinex


@pytest.mark.slow
def test_instantiate(quinex):
    """Quinex can be instantiated."""
    assert quinex is not None


@pytest.mark.slow
def test_pipeline(quinex):
    """Pipeline returns correct results for empty string, string without quantities, and string with quantities."""
    assert quinex("") == []
    assert quinex("This is a test string without any quantitative claim.") == []

    result = quinex(TEST_STR, skip_imprecise_quantities=True)
    assert len(result) == 2
    assert result[0]["claim"]["quantity"]["text"] == "100 meters"
    assert result[1]["claim"]["quantity"]["text"] == "10^5 Pa"


@pytest.mark.slow
def test_imprecise_quantities(quinex):
    """Pipeline detects imprecise quantities when skip_imprecise_quantities=False."""
    result = quinex(
        "We had a dozen of problems to discuss and presented several solutions, "
        "but a few issues remain unresolved.",
        skip_imprecise_quantities=False,
    )
    assert len(result) == 3
    assert result[0]["claim"]["quantity"]["text"] == "a dozen of problems"
    assert result[1]["claim"]["quantity"]["text"] == "several solutions"
    assert result[2]["claim"]["quantity"]["text"] == "a few issues"


@pytest.mark.slow
def test_char_offsets(quinex_with_empty):
    """Character offsets in predictions are self-consistent and match the source text."""
    result = quinex_with_empty(TEST_STR, skip_imprecise_quantities=True)
    for claim in result:
        all_predictions = list(claim["claim"].values()) + list(claim["qualifiers"].values())
        for p in all_predictions:
            assert p is not None, "Prediction must not be None."
            assert p["start"] <= p["end"], f"start > end for prediction: {p}"
            
            if p["is_implicit"]:
                assert p["start"] == 0 and p["end"] == 0, f"Implicit annotation must have offsets (0, 0): {p}"
            else:
                assert len(p["text"]) == 0 or p["end"] > 0, f"Non-empty explicit annotation must not have offsets (0, 0): {p}"
                assert TEST_STR[p["start"] : p["end"]] == p["text"], (
                    f"Mismatch between offsets and surface form: "
                    f"text[{p['start']}:{p['end']}] = '{TEST_STR[p['start']:p['end']]}' != '{p['text']}'"
                )


@pytest.mark.slow
def test_max_token_len_respected(quinex):
    """Pipeline respects the maximum token length of the context model when constructing the model input."""
    with open(Path(__file__).parent / "test_paper.txt", "r") as f:
        long_test_str = f.read()

    token_approx = len(long_test_str) / 4
    assert token_approx > 5 * 512, "Test paper must be larger than the model's context window."
    assert quinex(long_test_str) # TODO: Ensure quinex raises error in this test if context window exceeded


@pytest.mark.slow
def test_quantity_span_identification(quinex):
    """Quantity span identification extracts the expected spans from several hard-coded examples."""
    test_strs = [
        "The process offers very high purity levels of 99.97%–99.995% according to ISO-14687:2019.",
        "The liquefaction plants can produce LH2 by cooling hydrogen to −253 °C. This process is very energy-intensive, requiring up to 40% of the hydrogen's energy content (10–15 kWh/kgLH2) [25-28].",
        "The total pipeline length increases from 26 700 km (including the GH2 pipelines with diameters over 100 mm) in the Reference (no LH2) scenario to 28 300 km in the Comprehensive (high LH2) scenario.",
        "The results in roughly 0.062 EUR/kWh el for wind turbines and 0.026 EUR/ kWh el for open-field PV.",
        "After the backmapping of clustered sequences to cDNA, the full dataset consisted of 9,858,385 cDNA sequences.",
        "In particular, a CO 2 uptake is observed when using SIFSIX-3-Cu (1.24 mmol⋅g -1 ) at 298 K adsorption temp. and 0.4 mbar partial pressure.",
        "In year 2012, 98% of the energy consumption of the sector was covered by fuels [5] , 49.7% of which was diesel, 29.5% gasoline, 14.8% aviation fuels and 1.4% liquefied petroleum and natural gas [53].",
        "The 1,754.0 Å line is well resolved compared with the rest of the multiplet, and its intensity is well constrained to be 0.25 ± 0.04 of the total intensity of the multiplet.",
        "Well over one million OA papers were published in 2015.",
        "Consequently, hydrogen purities of 99.96 mol% can be achieved in the standard process. Further upstream purification and recycling steps make it possible to increase the hydrogen product purity to up to 99.999 mol%.",
    ]
    quantities = []
    for s in test_strs:
        quantities.extend(quinex.get_quantities(s))

    groundtruth = [
        "99.97%–99.995%",
        "−253 °C",
        "40%",
        "10–15 kWh/kgLH2",
        "26 700 km",
        "100 mm",
        "28 300 km",
        "0.062 EUR/kWh el",
        "0.026 EUR/ kWh el",
        "9,858,385 cDNA sequences",
        "1.24 mmol⋅g -1",
        "298 K",
        "0.4 mbar",
        "98%",
        "49.7%",
        "29.5%",
        "14.8%",
        "1.4%",
        "1,754.0 Å",
        "0.25 ± 0.04",
        "one million OA papers",
        "99.96 mol%",
        "99.999 mol%"
    ]
    for q, gt in zip(quantities, groundtruth):
        assert q["text"] in gt, f"Expected '{q['text']}' to be in '{gt}'"
