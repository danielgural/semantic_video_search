import fiftyone as fo
import fiftyone.operators as foo
from fiftyone.operators import types
from fiftyone.brain import Similarity
import time
import requests
import glob
from pprint import pprint
import os



class SemanticFrameSearch(foo.Operator):
    @property
    def config(self):
        return foo.OperatorConfig(
            name="semantic_frames_search",
            label="semantic frames search",
            description="semantic video search using only frames as context",
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

class SemanticVideoBackend(foo.Operator):
    @property
    def config(self):
        return foo.OperatorConfig(
            name="create_semantic_video_index",
            label="create semantic video index",
            description="create a semantic video index backend with Twelve Labs",
            dynamic=True,
            icon="/assets/search.svg",
        )
    
    def resolve_input(self, ctx):
        inputs = types.Object()
        target_view = get_target_view(ctx, inputs)
        inputs.message(
            "Notice", 
            label="Create Semantic Video Index", 
            description="Choose your index name and the modalities of embeddings you will use!"
        )
        inputs.str("index_name", label="Index_Name", required=True)
        inputs.view(
            "header", 
            types.Header(label="Select modalities for index", description="Select one or more from the below to extract embeddings from your videos", divider=True)
        )
        inputs.bool(
            "visual",
            label="visual",
            description="",
            view=types.CheckboxView(),
        )
        inputs.bool(
            "conversation",
            label="conversation",
            description="Video must have audio to work!",
            view=types.CheckboxView(),
        )
        inputs.bool(
            "text_in_video",
            label="text_in_video",
            description="",
            view=types.CheckboxView(),
        )
        inputs.bool(
            "logo",
            label="logo",
            description="",
            view=types.CheckboxView(),
        )

        inputs.view(
            "header2", 
            types.Header(label="Advise delegating to avoid timeout", description="", divider=True)
        )
        _execution_mode(ctx, inputs)
        return types.Property(inputs)
    
    def resolve_delegation(self, ctx):
        return ctx.params.get("delegate", False)
    
    def execute(self, ctx):
        ctx.dataset.compute_metadata()
        target = ctx.params.get("target", None)
        target_view = _get_target_view(ctx, target)

        API_URL = os.getenv("TWELVE_API_URL")
        API_KEY = os.getenv("TWELVE_API_KEY")

        if ctx.params.get("delegate", None):
            API_URL = ctx.params.get("TWELVE_API_URL", None)

            API_KEY = ctx.params.get("TWELVE_API_KEY", None)

        INDEX_NAME = ctx.params.get("index_name")

        INDEXES_URL = f"{API_URL}/indexes"

        headers = {
            "x-api-key": API_KEY
        }
        
        so = []

        if ctx.params.get("visual"):
            so.append("visual")
        if ctx.params.get("logo"):
            so.append("logo")
        if ctx.params.get("text_in_video"):
            so.append("text_in_video")
        if ctx.params.get("conversation"):
            so.append("conversation")

        data = {
        "engine_id": "marengo2.5",
        "index_options": so,
        "index_name": INDEX_NAME,
        }

        response = requests.post(INDEXES_URL, headers=headers, json=data)

        headers = {
            "x-api-key": API_KEY,
            "Content-Type": "application/json"
        } 

        INDEX_ID = get_twelve_id_from_name(INDEXES_URL, headers, INDEX_NAME)

        TASKS_URL = f"{API_URL}/tasks"

        videos = target_view
        for sample in videos:
            if sample.metadata.duration < 4:
                continue
            else:
                file_name = sample.filepath.split("/")[-1] 
                file_path = sample.filepath 
                file_stream = open(file_path,"rb")
            
                headers = {
                    "x-api-key": API_KEY
                }
            
                data = {
                    "index_id": INDEX_ID, 
                    "language": "en"
                }
            
                file_param=[
                    ("video_file", (file_name, file_stream, "application/octet-stream")),]
            
                response = requests.post(TASKS_URL, headers=headers, data=data, files=file_param)
                TASK_ID = response.json().get("_id")
                print (f"Status code: {response.status_code}")
                pprint (response.json())
            
                TASK_STATUS_URL = f"{API_URL}/tasks/{TASK_ID}"
                while True:
                    response = requests.get(TASK_STATUS_URL, headers=headers)
                    STATUS = response.json().get("status")
                    if STATUS == "ready":
                        break
                    time.sleep(10)
                
                VIDEO_ID = response.json().get('video_id')
                sample["Twelve Labs " + INDEX_NAME] = VIDEO_ID
                sample.save()
        return {}



class SemanticVideoSearch(foo.Operator):
    @property
    def config(self):
        return foo.OperatorConfig(
            name="semantic_video_search",
            label="semantic video search",
            description="semantic video search using videos as context",
            dynamic=True,
            icon="/assets/search.svg",
        )
    
    def resolve_input(self, ctx):
        inputs = types.Object()

        #API_URL = ctx.secret("TWELVE_API_URL")
        #API_KEY = ctx.secret("TWELVE_API_KEY")

        API_URL = os.getenv("TWELVE_API_URL")
        API_KEY = os.getenv("TWELVE_API_KEY")

        if API_URL is None or API_KEY is None:
            inputs.view(
                "warning", 
                types.Warning(label="Twelve Lab keys undefined", 
                description="Please define the enviroment variables TWELVE_API_KEY and TWELVE_API_URL and reload")
        )
        else:
            INDEXES_URL = f"{API_URL}/indexes"

            headers = {
                "x-api-key": API_KEY,
                "Content-Type": "application/json"
            } 

            response = requests.get(INDEXES_URL, headers=headers)



            if response.json()["data"] == []:
                inputs.view(
                    "No Index", 
                    types.Warning(label="No Indexes detected", 
                    description="Please run `create semantic video index` first in order to semantic search on your dataset!")
                )
            else:
            

            
                vis_flag = False
                logo_flag = False
                convo_flag = False
                text_flag = False

                index_info = {}
                for item in response.json()['data']:
                    if "visual" in item["index_options"]:
                        vis_flag = True
                    if "logo" in item["index_options"]:
                        logo_flag = True
                    if "text_in_video" in item["index_options"]:
                        text_flag = True
                    if "conversation" in item["index_options"]:
                        convo_flag = True
                    index_info[item['index_name']] = item['_id']
                
                choices = index_info.keys()
                choices_compare = [x[12:] for x in ctx.dataset.get_field_schema().keys()] #change if ever add more than Twelve Labs
                common_index = list(set(choices_compare) & set(choices))
                if len(common_index) < 1:
                    inputs.view(
                    "warning2", 
                    types.Warning(label="Twelve Lab Video ID Missing From Sample", 
                    description="Samples need to have a Twelve Lab Video ID associated with them.\
                    They are found in a field called Twelve Labs (index name). If this is missing from your dataset,\
                        make sure your dataset is persisent and to avoid losing between runs")
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
                                operator first! Note, you can only search on modalities within your chosen index!"
                    )
                    if len(choices) != len(common_index):
                        inputs.view(
                            "warning3", 
                            types.Warning(label="Only showing indexes that have Video IDs on the dataset.", 
                            description="To add video IDs, run create_semantic_video_index to regenerate the index. \
                                It will store the Video IDs in a field called Twelve Labs (index_name). If this is missing from your dataset,\
                                make sure your dataset is persisent and to avoid losing between runs")
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
                        types.Header(label="Select modalities for search", description="Select one or more from the below to search through your videos. Note: your index must have this modality!", divider=True)
                    )
                    if vis_flag:
                        inputs.bool(
                            "visual",
                            label="visual",
                            description="",
                            view=types.CheckboxView(),
                        )
                    if convo_flag:
                        inputs.bool(
                            "conversation",
                            label="conversation",
                            description="Video must have audio to work!",
                            view=types.CheckboxView(),
                        )
                    if text_flag:
                        inputs.bool(
                            "text_in_video",
                            label="text_in_video",
                            description="",
                            view=types.CheckboxView(),
                        )
                    if logo_flag:
                        inputs.bool(
                            "logo",
                            label="logo",
                            description="",
                            view=types.CheckboxView(),
                        )


                    _execution_mode(ctx, inputs)
        
        return types.Property(inputs)
    
    def resolve_delegation(self, ctx):
        return ctx.params.get("delegate", False)
    
    def execute(self, ctx):

        #API_URL = ctx.secrets["TWELVE_API_URL"]
        #API_KEY = ctx.secrets["TWELVE_API_KEY"]
        API_URL = os.getenv("TWELVE_API_URL")
        API_KEY = os.getenv("TWELVE_API_KEY")

        assert API_KEY, "Env variable TWELVE_API_KEY not defined."
        assert API_URL, "Env variable TWELVE_API_URL not defined."

        INDEX_NAME = ctx.params.get("index_name")

        INDEXES_URL = f"{API_URL}/indexes"

        headers = {
            "x-api-key": API_KEY,
            "Content-Type": "application/json"
        } 

        INDEX_ID = get_twelve_id_from_name(INDEXES_URL, headers, INDEX_NAME)
        prompt = ctx.params.get("prompt")
        SEARCH_URL = f"{API_URL}/search"

        headers = {
        "x-api-key": API_KEY
        }

        so = []

        if ctx.params.get("visual"):
            so.append("visual")
        if ctx.params.get("logo"):
            so.append("logo")
        if ctx.params.get("text_in_video"):
            so.append("text_in_video")
        if ctx.params.get("conversation"):
            so.append("conversation")

        data = {
        "query": prompt,
        "index_id": INDEX_ID,
        "search_options": so,
        }

        response = requests.post(SEARCH_URL, headers=headers, json=data)
        video_ids = [entry['video_id'] for entry in response.json()['data']]
        print(response.json())
        samples = []
        view1 = ctx.dataset.select_by("Twelve Labs " + INDEX_NAME, video_ids,ordered=True)
        start = [entry['start'] for entry in response.json()['data']]
        end = [entry['end'] for entry in response.json()['data']]
        if "results" in ctx.dataset.get_field_schema().keys():
            ctx.dataset.delete_sample_field("results")

        i=0
        for sample in view1:
            support = [int(start[i]*sample.metadata.frame_rate)+1 ,int(end[i]*sample.metadata.frame_rate)+1]
            sample["results"] = fo.TemporalDetection(label=prompt, support=tuple(support))
            sample.save()

        view2 = view1.to_clips("results")
        ctx.trigger("set_view", {"view": view2._serialize()})

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
                    "for more information"
                )
            ),
        )
        inputs.str("TWELVE_API_KEY", label="TWELVE_API_KEY", required=True)
        inputs.str("TWELVE_API_URL", label="TWELVE_API_URL", required=True)


    

def register(plugin):
    plugin.register(SemanticFrameSearch)
    plugin.register(SemanticVideoSearch)
    plugin.register(SemanticVideoBackend)