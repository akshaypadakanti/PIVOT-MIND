from django import forms


class PivotMindUploadForm(forms.Form):
    dataset_file = forms.FileField(
        label="Upload CSV Dataset",
        required=False,
        widget=forms.FileInput(attrs={"class": "input-file", "accept": ".csv,.xlsx,.xls"}),
    )
    demo_dataset = forms.ChoiceField(
        label="Or Choose a Demo Dataset",
        required=False,
        choices=[
            ("", "-- Select Demo Dataset --"),
            ("sales_performance.csv", "Global Sales & Profit Performance (CSV)"),
            ("customer_churn.csv", "SaaS Customer Churn & Usage Metrics (CSV)"),
            ("employee_attrition.csv", "HR Employee Attrition & Salary (CSV)"),
        ],
        widget=forms.Select(attrs={"class": "input-select"}),
    )
    user_query = forms.CharField(
        label="Custom Business Question (Optional - Leave blank for Autopilot Mode)",
        required=False,
        max_length=1000,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Leave empty for Autopilot Mode (Agent 3 will formulate hypotheses autonomously), or type a custom question...",
                "class": "input-area",
            }
        ),
    )

    def clean(self):
        cleaned_data = super().clean()
        file_obj = cleaned_data.get("dataset_file")
        demo = cleaned_data.get("demo_dataset")
        if not file_obj and not demo:
            raise forms.ValidationError("Please upload a CSV file or select a demo dataset.")
        return cleaned_data
