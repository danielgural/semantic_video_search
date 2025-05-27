# 🎥 FiftyOne + Twelve Labs Plugin

Bring multimodal video intelligence into your computer vision workflows with **FiftyOne** and **Twelve Labs**.

This plugin lets you generate rich video embeddings (visual, audio, OCR, conversation) using the Twelve Labs API and organize them into a **clip-level FiftyOne dataset** for analysis, search, and iteration.

> ⚡ Ideal for building your own retrieval pipelines, video QA systems, or semantic labeling tools on top of real clip-level understanding.

![semantic_video_search](https://github.com/danielgural/semantic_video_search/blob/main/assets/video_semantic_search.gif)

---

## ✨ Key Features

- 🧠 Generate multimodal embeddings from full videos  
- 🔄 Automatically split videos into meaningful **clips**  
- 📦 Store results in a new FiftyOne dataset with clip-level granularity  
- 🔍 Run **semantic search** over your indexed videos using prompts  
- 🔐 Uses secure secrets (`TL_API_KEY`) for easy API access  

---

## 📦 Installation

Install the plugin directly in FiftyOne:

```bash
fiftyone plugins download https://github.com/danielgural/semantic_video_search
```

---

## 🧩 Plugin Operators

### `create_twelve_labs_embeddings`

Generate embeddings for your videos via the [Twelve Labs API](https://twelvelabs.io). Videos are automatically split into clips, and the resulting dataset contains embeddings from selected modalities:

- `visual`  
- `audio`  

Each sample afterwards contains a [TemporalDetection](https://docs.voxel51.com/user_guide/using_datasets.html#temporal-detection) correlating to its embeddings. Turn your dataset into clips with [to_clips](https://docs.voxel51.com/user_guide/using_views.html#clip-views) to use as a normal embeddings! (More below!) 

> ☑️ Recommended to run as a **delegated operator** due to processing time.

---

### `create_twelve_labs_index`

Creates a searchable **Twelve Labs index** from your embedded clips. Choose your index name and embedding types. You can build indexes from:

- Entire dataset  
- Current view  
- Selected samples

Note, this builds the index in Twelve Labs!

---

### `twelve_labs_index_search`

Query your Twelve Labs index using a **natural language prompt**, and return results sorted by relevance. You can select one or more modalities to match (e.g., visual + audio + OCR).

Use this to semantically explore your video data while keeping data in Twelve Labs!

---

## 🔐 Environment Setup

You'll need a Twelve Labs API Key.

```bash
export TL_API_KEY=<YOUR_TWELVE_LABS_API_KEY>
```

You can also securely store it in the FiftyOne App as a **plugin secret**.

---

## 🔁 Example Workflow

1. **Generate clip-level embeddings**  
   Run `create_twelve_labs_embeddings` on a video dataset  
   → Creates a new dataset with embedded clips for more embedding awesomeness!

2. **Index your clips**  
   Run `create_twelve_labs_index` on the clip dataset  
   → Builds a searchable index with selected modalities that stays in Twelve Labs

3. **Search your videos**  
   Use `twelve_labs_index_search` with a prompt  
   → View most relevant clips inside FiftyOne!

---

## 📚 Resources

- [Twelve Labs API Docs](https://docs.twelvelabs.io/)  
- [FiftyOne Plugins Guide](https://docs.voxel51.com/plugins/using_plugins.html)  
- [Official Blog](https://voxel51.com/blog)


## Clip Dataset Conversion
```
import fiftyone.utils.video as fouv

def create_clip_dataset(
    dataset: fo.Dataset,
    clip_field: str,
    new_dataset_name: str = "clips",
    overwrite: bool = True,
    viz: bool = False,
    sim: bool = False,
) -> fo.Dataset:
    clips = []
    clip_view = dataset.to_clips(clip_field)
    clip_dataset = fo.Dataset(name=new_dataset_name,overwrite=overwrite)
    i = 0
    last_file = ""
    samples = []
    for clip in clip_view:

        out_path = clip.filepath.split(".")[0] + f"_{i}.mp4"
        fpath = clip.filepath 
        fouv.extract_clip(fpath, output_path=out_path, support=clip.support)
        clip.filepath = out_path
        samples.append(clip)
        clip.filepath = fpath
        if clip.filepath == last_file:
            i += 1
        else:
            i = 0
        last_file = clip.filepath
    clip_dataset.add_samples(samples)
    clip_dataset.add_sample_field("Twelve Labs Marengo-retrieval-27 Embeddings", fo.VectorField)
    clip_dataset.set_field("Twelve Labs Marengo-retrieval-27 Embeddings", clip_view.values("Twelve Labs Marengo-retrieval-27.embedding"))
    
    return clip_dataset
```

## 🪪 License

MIT
