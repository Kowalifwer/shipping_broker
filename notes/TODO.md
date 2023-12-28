## 19/12/2023 (post call notes)

1. comission - **cap at 5%**, unless if highly ranked, then excusable to go over
   1. perhaps first do the matching on other paramters - then do a comission filter.
2. port_from - location example of unstandardized input. "East Med/ Black Sea range"
   1. consider either training GPT to be more standardized, OR manually sort out SEAS and stuff, based on substring matches ?
3. Extract more emails from GPT, but only from the **past week** or so, and use to train and run some matches.


# 27/12/2023

1. normalize all gpt extracted fields? lowercase. fuzzy matching?

-> embeddings ->   

[Vector search | Redis](https://redis.io/docs/interact/search-and-query/query/vector-search/) ??

1. Create local embeddings, using best trained embeddings local model for now. For each SHIP and CARGO object, store the embeddings along the object.
2. For querying - ideally an IN-MEMORY database

# 28/12/2023

**New idea - HYBRID APPROACH**

1. Query simple fields like weight, capacity, month, capacity and other appropriate ones with simple DB queries - filter out stuff that has no chance of being relevant, and score it
2. Query more complex and diverse text fields like port to from, sea, and stuff via vector similarity search. This should better handle the diversity across semantically similar fields, example:  "Red Sea (can try redel Med)" will have similarity with red sea. Considered also fuzzy/similarity search, but vector should be more general
3. merge the scores of 2 approaches. tweak over time. both components can be improved with improving stage 1 - gpt to extract better info - i.e more fields for more embedding data, or better formatting/preprocessing/normalization of the simple db field (more consistent format)
4. Later, can see effectiveness of either, and make changes as necessary. Perhaps with fine tuning of the embedding model, there will be less need of the database querying step.
