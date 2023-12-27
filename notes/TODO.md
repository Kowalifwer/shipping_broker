## 19/12/2023 (post call notes)

1. comission - **cap at 5%**, unless if highly ranked, then excusable to go over
   1. perhaps first do the matching on other paramters - then do a comission filter.
2. port_from - location example of unstandardized input. "East Med/ Black Sea range"
   1. consider either training GPT to be more standardized, OR manually sort out SEAS and stuff, based on substring matches ?
3. Extract more emails from GPT, but only from the **past week** or so, and use to train and run some matches.


# 29/12/2023

1. normalize all gpt extracted fields? lowercase. fuzzy matching?

-> embeddings ->   

[Vector search | Redis](https://redis.io/docs/interact/search-and-query/query/vector-search/) ??

1. Create local embeddings, using best trained embeddings local model for now. For each SHIP and CARGO object, store the embeddings along the object.
2. For querying - ideally an IN-MEMORY database
