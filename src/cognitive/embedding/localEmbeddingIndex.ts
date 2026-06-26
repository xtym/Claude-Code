// Core types
export type EmbeddingIndexEntry = {
  id: string
  vector: Record<string, number> // term -> weight
  magnitude: number // pre-computed for cosine
  metadata?: Record<string, unknown>
}

export type ScoredResult = {
  id: string
  score: number
  metadata?: Record<string, unknown>
}

// Character n-grams (size 2-4) for sub-word tokenization
function extractCharNGrams(text: string, minN = 2, maxN = 4): string[] {
  const normalized = text.toLowerCase().replace(/\s+/g, ' ')
  const grams: string[] = []
  for (let n = minN; n <= maxN; n++) {
    for (let i = 0; i <= normalized.length - n; i++) {
      const gram = normalized.slice(i, i + n)
      if (/[a-z0-9]/.test(gram)) grams.push(gram)
    }
  }
  return grams
}

// TF-IDF computation
// tf(t,d) = 1 + log(freq(t,d)) or 0 if freq=0
// idf(t) = log(N / df(t))
// Each document vector is { term: tf-idf weight }
export function buildEmbeddingIndex(
  documents: { id: string; text: string; metadata?: Record<string, unknown> }[],
): EmbeddingIndexEntry[] {
  // Step 1: extract all n-grams and compute term frequencies
  const docNGrams: { id: string; ngrams: string[]; metadata?: Record<string, unknown> }[] =
    documents.map((doc) => ({
      id: doc.id,
      ngrams: extractCharNGrams(doc.text),
      metadata: doc.metadata,
    }))

  // Step 2: compute document frequency for each n-gram
  const docFreq: Record<string, number> = {}
  for (const doc of docNGrams) {
    const uniqueNGrams = new Set(doc.ngrams)
    for (const gram of uniqueNGrams) {
      docFreq[gram] = (docFreq[gram] ?? 0) + 1
    }
  }

  const N = docNGrams.length

  // Step 3: compute TF-IDF vectors
  return docNGrams.map((doc) => {
    // Term frequency within document
    const tf: Record<string, number> = {}
    for (const gram of doc.ngrams) {
      tf[gram] = (tf[gram] ?? 0) + 1
    }

    // TF-IDF: tf * idf where tf = 1 + log(freq), idf = log(N/df)
    const vector: Record<string, number> = {}
    let sumSquares = 0
    for (const [gram, freq] of Object.entries(tf)) {
      const tfidf = (1 + Math.log(freq)) * Math.log(1 + N / (docFreq[gram] ?? 1))
      vector[gram] = tfidf
      sumSquares += tfidf * tfidf
    }

    return {
      id: doc.id,
      vector,
      magnitude: Math.sqrt(sumSquares),
      metadata: doc.metadata,
    }
  })
}

// Query the index: build query vector, compute cosine similarity with each entry
export function queryEmbeddingIndex(
  index: EmbeddingIndexEntry[],
  query: string,
  topK: number,
): ScoredResult[] {
  const queryGrams = extractCharNGrams(query)

  // Build query TF vector (no IDF since query is one document)
  const queryTF: Record<string, number> = {}
  for (const gram of queryGrams) {
    queryTF[gram] = (queryTF[gram] ?? 0) + 1
  }

  // For query, use the same IDF weights from the corpus
  // But we don't have corpus stats here. Use sublinear TF instead.
  let queryMagnitude = 0
  const queryVector: Record<string, number> = {}
  for (const [gram, freq] of Object.entries(queryTF)) {
    const weight = 1 + Math.log(freq) // sublinear TF
    queryVector[gram] = weight
    queryMagnitude += weight * weight
  }
  queryMagnitude = Math.sqrt(queryMagnitude)

  if (queryMagnitude === 0) return []

  // Compute cosine similarity
  const scored: ScoredResult[] = []
  for (const entry of index) {
    if (entry.magnitude === 0) continue

    let dotProduct = 0
    for (const [gram, weight] of Object.entries(queryVector)) {
      const docWeight = entry.vector[gram]
      if (docWeight !== undefined) {
        dotProduct += weight * docWeight
      }
    }

    const similarity = dotProduct / (queryMagnitude * entry.magnitude)
    if (similarity > 0) {
      scored.push({ id: entry.id, score: similarity, metadata: entry.metadata })
    }
  }

  return scored.sort((a, b) => b.score - a.score).slice(0, topK)
}

// Persist/load index as JSON
export function serializeIndex(entries: EmbeddingIndexEntry[]): string {
  return JSON.stringify(entries)
}

export function deserializeIndex(json: string): EmbeddingIndexEntry[] {
  return JSON.parse(json)
}
