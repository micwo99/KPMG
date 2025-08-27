from extract_fields import extract_fields_majority_vote
if __name__ == "__main__":
    with open("/Users/michaelwolhandler/Downloads/Home-Assignment-GenAI-KPMG-caf77ef40ad902ea29f5a1005ea5a70cface6259/phase1_data/283_ex1.pdf", "rb") as f:
        file_bytes = f.read()
    extract_fields_majority_vote(file_bytes, language_hint="he")

    with open("/Users/michaelwolhandler/Downloads/Home-Assignment-GenAI-KPMG-caf77ef40ad902ea29f5a1005ea5a70cface6259/phase1_data/283_ex2.pdf", "rb") as f:
        file_bytes = f.read()
    extract_fields_majority_vote(file_bytes, language_hint="he")

    with open("/Users/michaelwolhandler/Downloads/Home-Assignment-GenAI-KPMG-caf77ef40ad902ea29f5a1005ea5a70cface6259/phase1_data/283_ex3.pdf", "rb") as f:
        file_bytes = f.read()
    extract_fields_majority_vote(file_bytes, language_hint="he")