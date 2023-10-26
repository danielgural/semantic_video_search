import fiftyone as fo
import fiftyone.operators as foo
from fiftyone.operators import types
from fiftyone.brain import Similarity


class SemanticVideoSearch(foo.Operator):
    @property
    def config(self):
        return foo.OperatorConfig(
            name="semantic_video_search",
            label="semantic video search",
            description="semantic video search",
            dynamic=True,
            icon="/assets/search.svg",
        )
    
    def resolve_input(self, ctx):
        inputs = types.Object()
        get_brain_key(ctx, inputs)
        sort_choices = ["Sort Frames", "Sort Videos"] # replace with your choices

        sort_group = types.RadioGroup()

        for choice in sort_choices:
            sort_group.add_choice(choice, label=choice)

        inputs.enum(
            "sort_group",
            sort_group.values(),
            label="Select which to sort",
            description="Show individual frames or whole videos",
            view=types.RadioView(),
            default='Sort Videos',
            required=True,
        )
        inputs.str("prompt", label="Prompt", required=True)
        return types.Property(inputs)
    
    def execute(self, ctx):
        frames = ctx.dataset.to_frames(sample_frames=True)
        sort_group = ctx.params.get("sort_group")
        prompt = ctx.params.get("prompt")
        brain_key = ctx.params.get("brain_key")
        view = frames.sort_by_similarity(prompt, brain_key=brain_key)
        if sort_group == "Sort Frames":
            ctx.trigger("set_view", {"view": view._serialize()})
        else:
            sample_ids = view.distinct("sample_id")
            sorted_list = []
            for sample in view:
                if sample.sample_id not in sorted_list:
                    sorted_list.append(sample.sample_id)
            ctx.trigger("set_view", {"view": ctx.dataset.select(sorted_list,ordered=True)._serialize()})
        return {}

_BRAIN_RUN_TYPES = {
    "similarity": Similarity,
}


def get_brain_key(
    ctx,
    inputs,
    label="Brain key",
    description="Select a brain key",
    run_type="similarity",
    show_default=True,
):
    type = _BRAIN_RUN_TYPES.get(run_type, None)
    brain_keys = ctx.dataset.list_brain_runs(type=type)

    if not brain_keys:
        message = "This dataset has no text similarity brain runs"
        
        warning = types.Warning(
            label=message,
            description="https://docs.voxel51.com/user_guide/brain.html",
        )
        prop = inputs.view("warning", warning)
        prop.invalid = True

        return

    text_brain_keys = []
    for brain_key in brain_keys:
        info = ctx.dataset.get_brain_info(brain_key)
        if info.config.supports_prompts:
            text_brain_keys.append(brain_key)
    if len(text_brain_keys) < 1:
        message = "This dataset has no text similarity brain runs"
        
        warning = types.Warning(
            label=message,
            description="https://docs.voxel51.com/user_guide/brain.html",
        )
        prop = inputs.view("warning", warning)
        prop.invalid = True

        return
    
    choices = types.DropdownView()
    for brain_key in brain_keys:
        choices.add_choice(brain_key, label=brain_key)

    default = brain_keys[0] if show_default else None
    inputs.str(
        "brain_key",
        default=default,
        required=True,
        label=label,
        description=description,
        view=choices,
    )

    return ctx.params.get("brain_key", None)

def register(plugin):
    plugin.register(SemanticVideoSearch)