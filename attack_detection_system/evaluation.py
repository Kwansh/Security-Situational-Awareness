from sklearn.metrics import accuracy_score, recall_score, confusion_matrix

def evaluate(y_true, y_pred):
    acc = accuracy_score(y_true, y_pred)
    recall = recall_score(y_true, y_pred)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

    report = f"""
    ===== 模型评估报告 =====

    Accuracy: {acc:.4f}
    Recall: {recall:.4f}
    False Positive Rate: {fpr:.4f}
    """
    print(report)
    with open("results/evaluation_report.txt", "w") as f:
        f.write(report)