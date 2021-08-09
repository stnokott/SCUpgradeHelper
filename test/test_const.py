from const import fuzzy_search_min_score


def test_fuzzy_search_min_score():
    inputs = range(20)
    previous_output = -1
    for input_ in inputs:
        output = fuzzy_search_min_score(input_)
        if output < previous_output:
            raise AssertionError("Min scores need to increase, not decrease.")
        previous_output = output
