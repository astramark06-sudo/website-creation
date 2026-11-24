"""Native Django forms generated from the validated workspace schema."""
from django import forms

from scripts.creator_access import Role
from scripts.creator_relational import table_definition, validate_schema
from .services import records


def related_options(workspace, definition):
    schema = validate_schema(workspace.schema)
    options = {}
    for field in definition["fields"]:
        if field["type"] != "relation" or field["target"] in options:
            continue
        target = table_definition(schema, field["target"])
        label_field = next((f["id"] for f in target["fields"] if f["type"] == "text"), None)
        options[field["target"]] = [
            (str(row["id"]), (row["values"].get(label_field) or "Record") + " (#" + str(row["id"]) + ")")
            for row in records(workspace, target["id"])
        ]
    return options


class RecordForm(forms.Form):
    def __init__(self, definition, options, *args, values=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.definition = definition
        for field in definition["fields"]:
            key, label, kind = "f_" + field["id"], field["label"], field["type"]
            if kind == "text":
                control = forms.CharField(label=label, max_length=160, required=False, strip=False,
                                          widget=forms.Textarea(attrs={"rows": 2}))
                initial = ""
            elif kind == "integer":
                control = forms.IntegerField(label=label, min_value=0, max_value=1000000)
                initial = 0
            elif kind == "choice":
                control = forms.ChoiceField(label=label, choices=[(choice, choice) for choice in field["choices"]])
                initial = field["choices"][0]
            else:
                control = forms.TypedChoiceField(label=label, required=False, coerce=int, empty_value=None,
                                                 choices=[("", "No related record"), *options[field["target"]]])
                initial = ""
            self.fields[key] = control
            self.initial[key] = values[field["id"]] if values is not None else initial

    def values(self):
        return {field["id"]: self.cleaned_data["f_" + field["id"]] for field in self.definition["fields"]}


class MemberForm(forms.Form):
    user_id = forms.IntegerField(label="Existing test account ID", min_value=1, max_value=2**53-1)
    role = forms.ChoiceField(choices=[(role.value, role.value.title()) for role in Role])
    active = forms.BooleanField(required=False, initial=True, label="Active membership")
