from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

#Our sentences we like to encode
sentences = [
    'This framework generates embeddings for each input sentence',
    'Sentences are passed as a list of string.',
    'The quick brown fox jumps over the lazy dog.',
    'Lazy Dog bro'
]

#Sentences are encoded by calling model.encode()
embeddings = model.encode(sentences)

# Example query vector
query_vector = model.encode(['Lazy Dog bro'])[0]

# Calculate cosine similarity between the query vector and the list of vectors
similarity_scores = cosine_similarity([query_vector], embeddings)

# Get the indices that would sort the similarity scores in descending order
sorted_indices = np.argsort(similarity_scores[0])[::-1]

# Print the ranked sentences
for rank, index in enumerate(sorted_indices):
    sentence = sentences[index]
    score = similarity_scores[0][index]
    print(f"Rank {rank + 1}: Similarity Score with '{sentence}': {score}")