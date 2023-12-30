from sentence_transformers import SentenceTransformer

from sklearn.metrics.pairwise import cosine_similarity

model = SentenceTransformer('all-MiniLM-L6-v2')
model2 = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
# model = SentenceTransformer("dima-does-code/LaBSE-geonames-15K-MBML-5e-v2")
# model = SentenceTransformer('chbwang/geo_multi-qa-mpnet-base-dot-v1')

# model2 = SentenceTransformer("DataQueen/LAPSE_GEONAMES_RELOC")

#Our sentences we like to encode
sentences = [
    "Indian Ocean",
    "China Sea",
    "East Sea",
    "Asian Sea",
    "South Asia Sea",
    "South China",
    "Mediterranean Sea",
    "Black Sea",
]

# sentences = [
#     "China",
#     # put some cities in china
#     "Beijing",
#     "Shanghai",
#     "Tianjin",

#     # put some random non china cities
#     "London",
#     "Paris",
#     "New York",
#     "Tokyo",

#     # put some japan cities

#     "Osaka",
#     "Kyoto",
#     "Yokohama",
# ]

#Sentences are encoded by calling model.encode()
embeddings = model.encode(sentences)
embeddings2 = model2.encode(sentences)

print(len(embeddings[0]))

query_str = "China/Japan"
# query_str = "Black Sea range or med sea"
# query_str = "East Med/ Black Sea range"
# Example query vector
query_vector = model.encode([query_str])[0]
query_vector2 = model2.encode([query_str])[0]

# Calculate cosine similarity between the query vector and the list of vectors
similarity_scores = cosine_similarity([query_vector], embeddings)
similarity_scores_2 = cosine_similarity([query_vector2], embeddings2)

# Output the sentence and its score, and its rank in the list
for i in range(len(sentences)):
    print(f"{sentences[i]} \t {similarity_scores[0][i]} \t {similarity_scores_2[0][i]}")