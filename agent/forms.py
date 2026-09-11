from django import forms


class AgentQueryForm(forms.Form):
    query = forms.CharField(
        label="Ask the Agent",
        min_length=2,
        max_length=4000,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Ask your question here...",
                "class": "input-area js-prompt",
            }
        ),
    )

    def clean_query(self):
        query = self.cleaned_data["query"].strip()
        if not query:
            raise forms.ValidationError("Please enter a question for the agent.")
        return query


class ToolPlaygroundForm(forms.Form):
    tool = forms.ChoiceField(
        label="Tool",
        widget=forms.Select(attrs={"class": "input-select"}),
    )
    input_data = forms.CharField(
        label="Input",
        required=False,
        max_length=8000,
        widget=forms.Textarea(
            attrs={
                "rows": 6,
                "placeholder": "Enter a value, city, query, JSON, or a JSON object of arguments.",
                "class": "input-area",
            }
        ),
    )

    def __init__(self, *args, tool_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tool"].choices = tool_choices or []

    def clean_input_data(self):
        return (self.cleaned_data.get("input_data") or "").strip()


class ChallengeQueryForm(forms.Form):
    query = forms.CharField(
        label="Your challenge query",
        min_length=2,
        max_length=4000,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Write the query you would send to the agent...",
                "class": "input-area js-prompt",
            }
        ),
    )

    def clean_query(self):
        query = self.cleaned_data["query"].strip()
        if not query:
            raise forms.ValidationError("Please submit a query for this challenge.")
        return query


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

