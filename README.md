## Semantic Video Search

![semantic_video_search](https://github.com/danielgural/semantic_video_search/blob/main/assets/sort_by_video.gif)

This plugin is a Python plugin that allows for you to semantically search your video datasets by frames or by video!

🔎 With a single prompt, find exactly what you are looking for across every frame in your dataset!

## Installation

```shell
fiftyone plugins download https://github.com/danielgural/semantic_video_search
```

## Operators

### `semantic_video_search`

Sorts based on a prompt through your video dataset for the most similar frames or videos by using a similiarty index of your choice. You can even use Vector DB backends such as Qdrant, Pinecone, Milvus, or LanceDB. Sort your frames as seen below, or by full video!

![frames](https://github.com/danielgural/semantic_video_search/blob/main/assets/sort_by_frames.gif)

Any text similarity index should be computed before hand using [FiftyOne Brain's Compute Similarity](https://docs.voxel51.com/user_guide/brain.html#text-similarity). The similarity index should also be on the frames of the image, in order to properly generate image embeddings. 

Heres an example:
```
import fiftyone as fo
import fiftyone.zoo as foz
import fiftyone.brain as fob

dataset = foz.load_zoo_dataset("quickstart-video")
frames = dataset.to_frames(sample_frames=True)

results= fob.compute_similarity(
    frames,
    model="clip-vit-base32-torch",
    brain_key="sim",
)

session = fo.launch_app(frames) #run plugin
```
