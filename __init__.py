import fiftyone as fo
import fiftyone.operators as foo
from fiftyone.operators import types
from fiftyone.brain import Similarity
import time
import requests
import glob
from pprint import pprint
import os
from twelvelabs import TwelveLabs


class CreateTwelveLabsEmbeddings(foo.Operator):
    @property
    def config(self):
        return foo.OperatorConfig(
            name="create_twelve_labs_embeddings",
            label="Create Twelve Labs Embeddings",
            description="Store Twelve Labs embeddings on your videos in a new Clips dataset",
            dynamic=True,
            icon="/assets/search.svg",
        )

    def resolve_input(self, ctx):
        inputs = types.Object()
        API_KEY = ctx.secret("TL_API_KEY")

        # API_URL = os.getenv("TWELVE_API_URL")
        # API_KEY = os.getenv("TWELVE_API_KEY")

        if API_KEY is None:
            inputs.view(
                "warning",
                types.Warning(
                    label="Twelve Lab key undefined",
                    description="Please define the enviroment variables TL_API_KEY and reload",
                ),
            )

        target_view = get_target_view(ctx, inputs)
        inputs.view(
            "header",
            types.Header(
                label="Select modalities for embedding generation",
                description="Select one or more from the below to extract embeddings from your videos",
                divider=True,
            ),
        )
        inputs.bool(
            "visual",
            label="visual",
            description="",
            view=types.CheckboxView(),
        )
        inputs.bool(
            "audio",
            label="audio",
            description="Video must have audio to work!",
            view=types.CheckboxView(),
        )

        inputs.view(
            "header2",
            types.Header(
                label="Advise delegating to avoid timeout", description="", divider=True
            ),
        )
        _execution_mode(ctx, inputs)
        return types.Property(inputs)

    def resolve_delegation(self, ctx):
        return ctx.params.get("delegate", False)

    def execute(self, ctx):

        ctx.dataset.compute_metadata()
        target = ctx.params.get("target", None)
        target_view = _get_target_view(ctx, target)

        API_KEY = ctx.secret("TL_API_KEY")
        # API_KEY = os.getenv("TL_API_KEY")

        client = TwelveLabs(api_key=API_KEY)

        so = []

        if ctx.params.get("visual"):
            so.append("visual")
        if ctx.params.get("audio"):
            so.append("audio")

        models = [{"name": "marengo2.7", "options": so}]

        videos = target_view
        for sample in videos:
            if sample.metadata.duration < 4 or sample.metadata.duration > 7200:
                continue
            else:
                file_name = sample.filepath.split("/")[-1]
                file_path = sample.filepath

                task = client.embed.task.create(
                    model_name="Marengo-retrieval-2.7",
                    video_file=file_path,
                )

                def on_task_update(task):
                    print(f"  Status={task.status}")

                task.wait_for_done(sleep_interval=5, callback=on_task_update)

                if task.status != "ready":
                    raise RuntimeError(f"Indexing failed with status {task.status}")

                retrieved_task = task.retrieve(
                    embedding_option=["visual-text", "audio"]
                )
                i = 0
                dets = []
                for segment in retrieved_task.video_embedding.segments:
                    det = fo.TemporalDetection.from_timestamps(
                        [segment.start_offset_sec, segment.end_offset_sec],
                        label=f"segment_{i}",
                        sample=sample,
                    )

                    i += 1
                    det.embedding = segment.embeddings_float
                    dets.append(det)

                sample["Twelve Labs Marengo-retrieval-27"] = fo.TemporalDetections(
                    detections=dets
                )
                sample.save()
        return {}


class TwelveLabsSemanticSearch(foo.Operator):
    @property
    def config(self):
        return foo.OperatorConfig(
            name="twelve_labs_semantic_search",
            label="Twelve Labs Semantic Search",
            description="Semantic video search using videos as context and local Twelve Labs Embeddings",
            dynamic=True,
            icon="/assets/search.svg",
        )

    def resolve_input(self, ctx):
        inputs = types.Object()

        API_KEY = ctx.secret("TL_API_KEY")

        if API_KEY is None:
            inputs.view(
                "warning",
                types.Warning(
                    label="Twelve Lab key undefined",
                    description="Please define the enviroment variables TL_API_KEY and reload",
                ),
            )
        else:
            target_view = get_target_view(ctx, inputs)
            client = TwelveLabs(api_key=API_KEY)
            indexes = client.index.list()

            if not any(
                field.startswith("Twelve Labs")
                for field in list(ctx.dataset.get_field_schema().keys())
            ):
                inputs.view(
                    "No Embeddings",
                    types.Warning(
                        label="No embeddings detected",
                        description="Please run `create twelve labs embeddings` first in order to semantic search on your dataset!",
                    ),
                )
            else:

                inputs.str("prompt", label="Prompt", required=True)

                _execution_mode(ctx, inputs)

        return types.Property(inputs)

    def resolve_delegation(self, ctx):
        return ctx.params.get("delegate", False)

    def execute(self, ctx):

        API_KEY = ctx.secret("TL_API_KEY")

        assert API_KEY, "Env variable TL_API_KEY not defined."

        target = ctx.params.get("target", None)
        target_view = _get_target_view(ctx, target)

        client = TwelveLabs(api_key=API_KEY)

        prompt = ctx.params.get("prompt")

        res = client.embed.create(
            model_name="Marengo-retrieval-2.7",
            text=prompt,
        )

        
        print(f"Found {len(video_ids)} videos")
        samples = []
        view1 = target_view.select_by(
            "Twelve Labs " + index_name, video_ids, ordered=True
        )
        print(f"Found {len(view1)} samples")
        start = [entry.start for entry in search_results.data]
        end = [entry.end for entry in search_results.data]
        if "results" in ctx.dataset.get_field_schema().keys():
            ctx.dataset.delete_sample_field("results")

        i = 0
        for sample in view1:
            support = [
                int(start[i] * sample.metadata.frame_rate) + 1,
                int(end[i] * sample.metadata.frame_rate) + 1,
            ]
            sample["results"] = fo.TemporalDetection(
                label=prompt, support=tuple(support)
            )
            sample.save()

        view2 = view1.to_clips("results")
        ctx.trigger("set_view", {"view": view2._serialize()})
        ctx.ops.set_view(view=view2)
        return {}


class CreateTwelveLabsIndex(foo.Operator):
    @property
    def config(self):
        return foo.OperatorConfig(
            name="create_twelve_labs_index",
            label="Create Twelve Labs index",
            description="Create a Twelve Labs index backend",
            dynamic=True,
            icon="/assets/search.svg",
        )

    def resolve_input(self, ctx):
        inputs = types.Object()
        API_KEY = ctx.secret("TL_API_KEY")

        # API_URL = os.getenv("TWELVE_API_URL")
        # API_KEY = os.getenv("TWELVE_API_KEY")

        if API_KEY is None:
            inputs.view(
                "warning",
                types.Warning(
                    label="Twelve Lab key undefined",
                    description="Please define the enviroment variables TL_API_KEY and reload",
                ),
            )

        target_view = get_target_view(ctx, inputs)
        inputs.message(
            "Notice",
            label="Create Twelve Labs Index",
            description="Choose your index name and the modalities of embeddings you will use!",
        )
        inputs.str("index_name", label="Index_Name", required=True)
        inputs.view(
            "header",
            types.Header(
                label="Select modalities for index",
                description="Select one or more from the below to extract embeddings from your videos",
                divider=True,
            ),
        )
        inputs.bool(
            "visual",
            label="visual",
            description="",
            view=types.CheckboxView(),
        )
        inputs.bool(
            "audio",
            label="audio",
            description="Video must have audio to work!",
            view=types.CheckboxView(),
        )

        inputs.view(
            "header2",
            types.Header(
                label="Advise delegating to avoid timeout", description="", divider=True
            ),
        )
        _execution_mode(ctx, inputs)
        return types.Property(inputs)

    def resolve_delegation(self, ctx):
        return ctx.params.get("delegate", False)

    def execute(self, ctx):
        ctx.dataset.compute_metadata()
        target = ctx.params.get("target", None)
        target_view = _get_target_view(ctx, target)

        API_KEY = ctx.secret("TL_API_KEY")
        # API_KEY = os.getenv("TL_API_KEY")

        INDEX_NAME = ctx.params.get("index_name")

        client = TwelveLabs(api_key=API_KEY)

        so = []

        if ctx.params.get("visual"):
            so.append("visual")
        if ctx.params.get("audio"):
            so.append("audio")

        models = [{"name": "marengo2.7", "options": so}]

        index = client.index.create(
            name=INDEX_NAME,
            models=models,
        )

        index_id = index.id

        videos = target_view
        for sample in videos:
            if sample.metadata.duration < 4 or sample.metadata.duration > 7200:
                continue
            else:
                file_name = sample.filepath.split("/")[-1]
                file_path = sample.filepath

                task = client.task.create(index_id=index_id, file=file_path)

                def on_task_update(task):
                    print(f"  Status={task.status}")

                task.wait_for_done(sleep_interval=5, callback=on_task_update)

                if task.status != "ready":
                    raise RuntimeError(f"Indexing failed with status {task.status}")

                video_id = task.video_id

                sample["Twelve Labs " + INDEX_NAME] = video_id
                sample.save()
        return {}


class TwelveLabsIndexSearch(foo.Operator):
    @property
    def config(self):
        return foo.OperatorConfig(
            name="twelve_labs_index_search",
            label="Twelve Labs Index Search",
            description="Semantic video search using videos as context and a Twelve Labs Index on the backend",
            dynamic=True,
            icon="/assets/search.svg",
        )

    def resolve_input(self, ctx):
        inputs = types.Object()

        API_KEY = ctx.secret("TL_API_KEY")

        if API_KEY is None:
            inputs.view(
                "warning",
                types.Warning(
                    label="Twelve Lab key undefined",
                    description="Please define the enviroment variables TL_API_KEY and reload",
                ),
            )
        else:
            target_view = get_target_view(ctx, inputs)
            client = TwelveLabs(api_key=API_KEY)
            indexes = client.index.list()

            if indexes == []:
                inputs.view(
                    "No Index",
                    types.Warning(
                        label="No Indexes detected",
                        description="Please run `create semantic video index` first in order to semantic search on your dataset!",
                    ),
                )
            else:

                vis_flag = False
                audio_flag = False

                index_info = {}
                indexes[0].models.root[0].options
                for index in indexes:
                    if "visual" in index.models.root[0].options:
                        vis_flag = True
                    if "audio" in index.models.root[0].options:
                        audio_flag = True
                    index_info[index.name] = index.id

                choices = index_info.keys()
                choices_compare = [
                    x[12:] for x in ctx.dataset.get_field_schema().keys()
                ]  # change if ever add more than Twelve Labs
                common_index = list(set(choices_compare) & set(choices))
                if len(common_index) < 1:
                    inputs.view(
                        "warning2",
                        types.Warning(
                            label="Twelve Lab Video ID Missing From Sample",
                            description="Samples need to have a Twelve Lab Video ID associated with them.\
                    They are found in a field called Twelve Labs (index name). If this is missing from your dataset,\
                        make sure your dataset is persisent and to avoid losing between runs",
                        ),
                    )
                else:

                    radio_group = types.RadioGroup()

                    for choice in common_index:
                        radio_group.add_choice(choice, label=choice)

                    inputs.message(
                        "Notice",
                        label="Semantic Video Search",
                        description="Search through your video dataset with a prompt. If you haven't yet \
                            generated a similarity index with Twelve Labs, run the creaet semantic video index \
                                operator first! Note, you can only search on modalities within your chosen index!",
                    )
                    if len(choices) != len(common_index):
                        inputs.view(
                            "warning3",
                            types.Warning(
                                label="Only showing indexes that have Video IDs on the dataset.",
                                description="To add video IDs, run create_semantic_video_index to regenerate the index. \
                                It will store the Video IDs in a field called Twelve Labs (index_name). If this is missing from your dataset,\
                                make sure your dataset is persisent and to avoid losing between runs",
                            ),
                        )
                    inputs.enum(
                        "index_name",
                        radio_group.values(),
                        label="Pick an index",
                        description="",
                        view=types.DropdownView(),
                        required=True,
                    )
                    inputs.str("prompt", label="Prompt", required=True)

                    inputs.view(
                        "header",
                        types.Header(
                            label="Select modalities for search",
                            description="Select one or more from the below to search through your videos. Note: your index must have this modality!",
                            divider=True,
                        ),
                    )
                    if vis_flag:
                        inputs.bool(
                            "visual",
                            label="visual",
                            description="",
                            view=types.CheckboxView(),
                        )
                    if audio_flag:
                        inputs.bool(
                            "audio",
                            label="audio",
                            description="Video must have audio to work!",
                            view=types.CheckboxView(),
                        )

                    _execution_mode(ctx, inputs)

        return types.Property(inputs)

    def resolve_delegation(self, ctx):
        return ctx.params.get("delegate", False)

    def execute(self, ctx):

        API_KEY = ctx.secret("TL_API_KEY")

        assert API_KEY, "Env variable TL_API_KEY not defined."

        target = ctx.params.get("target", None)
        target_view = _get_target_view(ctx, target)

        client = TwelveLabs(api_key=API_KEY)

        index_name = ctx.params.get("index_name")

        indexes = client.index.list()
        for index in indexes:
            if index.name == index_name:
                index_id = index.id

        prompt = ctx.params.get("prompt")

        so = []

        if ctx.params.get("visual"):
            so.append("visual")
        if ctx.params.get("audio"):
            so.append("audio")

        if len(so) >= 2:
            search_results = client.search.query(
                index_id=index_id, query_text=prompt, options=so, operator="and"
            )
        else:
            search_results = client.search.query(
                index_id=index_id, query_text=prompt, options=so
            )

        video_ids = [entry.video_id for entry in search_results.data]
        print(f"Found {len(video_ids)} videos")
        samples = []
        view1 = target_view.select_by(
            "Twelve Labs " + index_name, video_ids, ordered=True
        )
        print(f"Found {len(view1)} samples")
        start = [entry.start for entry in search_results.data]
        end = [entry.end for entry in search_results.data]
        if "results" in ctx.dataset.get_field_schema().keys():
            ctx.dataset.delete_sample_field("results")

        i = 0
        for sample in view1:
            support = [
                int(start[i] * sample.metadata.frame_rate) + 1,
                int(end[i] * sample.metadata.frame_rate) + 1,
            ]
            sample["results"] = fo.TemporalDetection(
                label=prompt, support=tuple(support)
            )
            sample.save()

        view2 = view1.to_clips("results")
        ctx.trigger("set_view", {"view": view2._serialize()})
        ctx.ops.set_view(view=view2)
        return {}


def get_target_view(ctx, inputs):
    has_view = ctx.view != ctx.dataset.view()
    has_selected = bool(ctx.selected)
    default_target = None

    if has_view or has_selected:
        target_choices = types.RadioGroup(orientation="horizontal")
        target_choices.add_choice(
            "DATASET",
            label="Entire dataset",
            description="Process the entire dataset",
        )

        if has_view:
            target_choices.add_choice(
                "CURRENT_VIEW",
                label="Current view",
                description="Process the current view",
            )
            default_target = "CURRENT_VIEW"

        if has_selected:
            target_choices.add_choice(
                "SELECTED_SAMPLES",
                label="Selected samples",
                description="Process only the selected samples",
            )
            default_target = "SELECTED_SAMPLES"

        inputs.enum(
            "target",
            target_choices.values(),
            default=default_target,
            required=True,
            label="Target view",
            view=target_choices,
        )

    target = ctx.params.get("target", default_target)

    return _get_target_view(ctx, target)


def _get_target_view(ctx, target):
    if target == "SELECTED_SAMPLES":
        return ctx.view.select(ctx.selected)

    if target == "DATASET":
        return ctx.dataset

    return ctx.view


def get_twelve_id_from_name(INDEXES_URL, headers, INDEX_NAME):
    response = requests.get(INDEXES_URL, headers=headers)
    INDEX_ID = None
    for index in response.json()["data"]:
        if index["index_name"] == INDEX_NAME:
            INDEX_ID = index["_id"]
    return INDEX_ID


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


def _execution_mode(ctx, inputs):
    delegate = ctx.params.get("delegate", False)

    if delegate:
        description = "Uncheck this box to execute the operation immediately"
    else:
        description = "Check this box to delegate execution of this task"

    inputs.bool(
        "delegate",
        default=False,
        required=True,
        label="Delegate execution?",
        description=description,
        view=types.CheckboxView(),
    )

    if delegate:
        inputs.view(
            "notice",
            types.Notice(
                label=(
                    "You've chosen delegated execution. Note that you must "
                    "have a delegated operation service running in order for "
                    "this task to be processed. See "
                    "https://docs.voxel51.com/plugins/index.html#operators "
                    "for more information. Also, dont forget to set enviroment variables in the delegated enviroment as well!"
                )
            ),
        )


def register(plugin):
    plugin.register(TwelveLabsIndexSearch)
    plugin.register(CreateTwelveLabsEmbeddings)
    plugin.register(CreateTwelveLabsIndex)
