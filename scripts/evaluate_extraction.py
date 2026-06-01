import argparse
import json
import os
from typing import Dict, Any

try:
    from rouge_score import rouge_scorer
except ImportError:
    print("Please install rouge-score: uv pip install rouge-score")
    exit(1)


def calculate_f1(pred_tokens, ref_tokens):
    if not pred_tokens or not ref_tokens:
        return 0.0
    common = set(pred_tokens) & set(ref_tokens)
    if not common:
        return 0.0
    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(ref_tokens)
    return 2 * (precision * recall) / (precision + recall)


def evaluate_extraction(prediction_file: str, ground_truth_file: str):
    print(f"Evaluating {prediction_file} against {ground_truth_file}...")
    
    with open(prediction_file, "r", encoding="utf-8") as f:
        preds = json.load(f)
    with open(ground_truth_file, "r", encoding="utf-8") as f:
        truths = json.load(f)

    scorer = rouge_scorer.RougeScorer(['rouge1', 'rougeL'], use_stemmer=True)
    
    total_rouge1 = 0
    total_rougeL = 0
    total_f1 = 0
    count = 0

    for pmid, pred_data in preds.items():
        if pmid not in truths:
            continue
            
        truth_data = truths[pmid]
        
        # Compare key PICO elements
        for key in ['population', 'intervention', 'outcome']:
            if key in pred_data and key in truth_data:
                pred_text = str(pred_data[key])
                truth_text = str(truth_data[key])
                
                scores = scorer.score(truth_text, pred_text)
                total_rouge1 += scores['rouge1'].fmeasure
                total_rougeL += scores['rougeL'].fmeasure
                
                pred_toks = pred_text.lower().split()
                truth_toks = truth_text.lower().split()
                total_f1 += calculate_f1(pred_toks, truth_toks)
                
                count += 1

    if count == 0:
        print("No matching data points found for evaluation.")
        return

    print("\n--- Evaluation Results ---")
    print(f"Data points evaluated: {count}")
    print(f"Average ROUGE-1 F-Measure: {total_rouge1 / count:.4f}")
    print(f"Average ROUGE-L F-Measure: {total_rougeL / count:.4f}")
    print(f"Average Token F1 Score:    {total_f1 / count:.4f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate PICO extraction performance.")
    parser.add_argument("--preds", required=True, help="Path to predictions JSON")
    parser.add_argument("--truth", required=True, help="Path to ground truth JSON")
    args = parser.parse_args()
    
    evaluate_extraction(args.preds, args.truth)
