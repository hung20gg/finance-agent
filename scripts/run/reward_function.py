import re
import math
import json

# Extract <answer> ... </answer> from the response


# Extract <tool_call> ... </tool_call> from the response
def extract_tool_call(response: str) -> list[str]:     
    matches = re.findall(r"<tool_call>(.*?)</tool_call>", response, re.DOTALL)
    return [m.strip() for m in matches]
    


def chi2_pdf(x, df=15):
    if x < 0:
        return 0.0
    
    coef = 1.0 / ( (2 ** (df / 2.0)) * math.gamma(df / 2.0) )
    return coef * (x ** (df / 2.0 - 1.0)) * math.exp(-x / 2.0)


def extract_boxed_answer(text):
    matches = re.findall(r'\\boxed\{([^}]*)\}', text)
    
    if not matches:
        return None
    
    content = matches[-1].strip()  # take the last box
    
    # Try to convert to float
    try:
        num = float(content)
        return round(num, 2)
    except:
        return content

def compute_score(solution_str, ground_truth):

    tool_calls = extract_tool_call(solution_str)
    pred = extract_boxed_answer(solution_str)

        
    ans = solution_str.split("</tool_call>")[-1].split("</think>")[-1] # crude way to get the answer part after the last tool call
    
    
    if len(tool_calls) == 0:
        return {
            "num_tool_calls": len(tool_calls),
            "total_score": 0,
            "error": "No tools called",
            "ground_truth": ground_truth,
            "pred": pred
        }
    
    
    def round_sig(x, sig=5):
        if x == 0:
            return 0
        return round(x, sig - int(math.floor(math.log10(abs(x)))) - 1)


    if type(pred) != type(ground_truth):
        label = False

    elif isinstance(ground_truth, str):
        label = pred == ground_truth

    

    elif isinstance(ground_truth, float):
        eps = 0.01
        if ground_truth > 10:
            eps = 0.001 * ground_truth 
        gt = round_sig(ground_truth, 4)
        pr = round_sig(pred, 4)
        print(f"### Ground truth: {gt}, Pred: {pr}, Epsilon: {eps}")
        label = abs(gt - pr) <= eps

    elif isinstance(ground_truth, int):
        label = pred == ground_truth

    else:
        label = False

    score = 1 if label else 0


    print(f"### Extracted answer: {pred}, ground truth: {ground_truth}, score: {score}")
    
    return {
        "num_tool_calls": len(tool_calls),
        "total_score": score,
        "ground_truth": ground_truth,
        "pred": pred
    }