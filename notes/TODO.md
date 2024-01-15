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


# 14/01/2023

1. ship status handling
   1. open -> set month to be current month?
   2. employed -> ignore - means already occupied (ignore?)
   3. prompt -> same as open, but more urgent (perhaps slightly higher score than just OPEN)
2. GPT parsing month - perhaps enable whole DATE ? -> manually split into MONTH or exact date type, and score higher if exact is present
3. **Improve matching**
   1. Consider other embedding models for port + sea ? Perhaps let GPT collect a string of all location data into 1 field? - for better matching?
   2. How to handle missing fields ? (empty strings) - should objects with more fields be automatically ranked higher ? Conversely, how much to penalize missing fields? Depends on field importance I guess?
   3. Improve hard limits - currently even with big score detriment, system will still end up suggesting good cargo LOCATION-wise, but bad date for example. Perhaps do filter out stuff that will never work, out of the original dataset.
   4. Consider alternative matching approach - AVERAGE RANKING (i.e rank individually based on the different conditions, and then merge into a single rank. Perhaps some individual rankings can have a higher weight than others. Intersecting high ranked objects should generally be good, right?)
   5. Not every ship will have N good enough rankings. Create a way to handle what scores are "good enough?". If ship does not have matches above this thereshold - then ignore this ship.
