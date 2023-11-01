## Semantic Video Search

![semantic_video_search](https://github.com/danielgural/semantic_video_search/blob/main/assets/video_semantic_search.gif)

This plugin is a Python plugin that allows for you to semantically search your video datasets by frames or by video!

🔎 With a single prompt, find exactly what you are looking for across every frame in your dataset!

## Installation

```shell
fiftyone plugins download https://github.com/danielgural/semantic_video_search
```

## Operators

### `semantic_video_search`

Sorts based on a prompt through your video dataset for the most similar videos by using a similiarty index of your choice. Use [Twelve Labs](https://twelvelabs.io/) to create an index of your videos to do video semantic search. You can generate the index with the `create semantic video index` operator. Search on four different embeddings: visual, text in video, conversations, and logos.

For more info on Twelve Labs Search, look [here](https://docs.twelvelabs.io/docs/search-single-queries)! Twelve Labs features a free tier so its easy to get started right away!

### `semantic_frames_search` 

Sorts based on a prompt through your video dataset using single frame embeddings. You will need to generate a similarity index with FiftyOne Brain with textual embeddings before hand. You can even use Vector DB backends such as Qdrant, Pinecone, Milvus, or LanceDB for frame based search. Sort your frames as seen below, or by full video!

![frames](https://github.com/danielgural/semantic_video_search/blob/main/assets/sort_by_frames.gif)

### `create_semantic_video_index`

Generates a [Twelve Labs](https://twelvelabs.io/) similarity index for you video dataset. You can change multiple parameters such as the types of embeddings to search on. The index must contain the embedding type in order to search on. You can also decide to upload your entire dataset, selected samples, or the current view to the database. It is highly recommended you [delegate](https://docs.voxel51.com/plugins/using_plugins.html#setting-up-an-orchestrator) this operator due to its long runtime. Also note that videos must be at least four seconds long!

## Video Semantic Search

To start using the Video Semantic Search, first generate a [Twelve Labs API Token](https://dashboard.twelvelabs.io/home). The token will be used by the plugin to access the Twelve Labs API. To set these variables, define them before running the app.

```
export API_KEY=<YOUR_API_KEY>
export API_URL=https://api.twelvelabs.io/v1.1
```

Alternatively, if you are running the operator as a delegated operator, you can pass them in through the app. 

![index](https://github.com/danielgural/semantic_video_search/blob/main/assets/create_index.png)

Choose the index name and the embeddings you would like to include in your index. After execution, videos will be uploaded and index will be created. Additionally, a new field with Twelve Labs + Index Name will be added to your sample to correlate a sample with a Twelve Labs UID.

After your index has been created, its time for search! To use semantic video search, input the index name you want to search on, the prompt you are searching through, and which embeddings to search through. Your index needs to have these embeddings in order to search. Afterwards, your dataset will be sorted based on the most similar samples!

Here's a quick demo below!

![sort](https://github.com/danielgural/semantic_video_search/blob/main/assets/sort_by_frames.gif)

## Semantic Frames Search

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

Afterwards, choose to sort by frames or videos. This determines what type of view, video or frames, is returned. Pass a prompt in and sort your dataset!

![sort_frames](https://github.com/danielgural/semantic_video_search/blob/main/assets/sort_by_video.gif)