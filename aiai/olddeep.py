import time
import re
import requests
import logging
import numpy as np
import torch
import json
import os
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from duckduckgo_search import DDGS
from transformers import AutoTokenizer, AutoModel
from typing import List, Dict, Tuple, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AdvancedEmbeddingModel:
    """A class to handle embeddings using a state-of-the-art HuggingFace model."""
    
    def __init__(self, model_name="nomic-ai/nomic-embed-text-v2-moe"):
        """Initialize the embedding model with a powerful embedding model."""
        logger.info(f"Loading embedding model: {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        self.model = AutoModel.from_pretrained(model_name, trust_remote_code=True)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)
        self.model.eval()  # Set model to evaluation mode
        self.dimension = self.model.config.hidden_size
        logger.info(f"Initialized embedding model on {self.device} with dimension {self.dimension}")
        
    def get_embeddings(self, texts: List[str], batch_size: int = 8) -> np.ndarray:
        """Generate embeddings for a list of texts with improved pooling strategy."""
        embeddings = []
        
        # Process in batches to avoid memory issues
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            # Prefix for E5 model to improve results
            prefixed_texts = [f"passage: {text}" for text in batch_texts]
            
            # Tokenize
            inputs = self.tokenizer(
                prefixed_texts, 
                padding=True, 
                truncation=True, 
                max_length=512, 
                return_tensors="pt"
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Generate embeddings
            with torch.no_grad():
                outputs = self.model(**inputs)
                
            # Advanced pooling strategy for E5 model
            attention_mask = inputs['attention_mask']
            token_embeddings = outputs.last_hidden_state
            
            # Mean pooling with attention mask
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
            sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
            batch_embeddings = sum_embeddings / sum_mask
            
            # Normalize embeddings (critical for E5 model)
            batch_embeddings = torch.nn.functional.normalize(batch_embeddings, p=2, dim=1)
            
            embeddings.append(batch_embeddings.cpu().numpy())
            
        return np.vstack(embeddings)

    def get_query_embedding(self, query: str) -> np.ndarray:
        """Generate embedding specifically for a query with special formatting."""
        # E5 requires "query: " prefix for queries
        formatted_query = f"query: {query}"
        inputs = self.tokenizer(
            formatted_query,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt"
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        # Get embeddings and normalize
        embeddings = outputs.last_hidden_state
        attention_mask = inputs['attention_mask']
        mask_expanded = attention_mask.unsqueeze(-1).expand(embeddings.size()).float()
        sum_embeddings = torch.sum(embeddings * mask_expanded, 1)
        sum_mask = torch.clamp(mask_expanded.sum(1), min=1e-9)
        mean_embedding = sum_embeddings / sum_mask
        normalized = torch.nn.functional.normalize(mean_embedding, p=2, dim=1)
        
        return normalized.cpu().numpy()


class ContentExtractor:
    """Class for extracting and cleaning content from web pages."""
    
    def __init__(self):
        """Initialize content extractor."""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    
    def extract_readable_content(self, url: str, timeout: int = 5) -> Optional[str]:
        """Extract main content from a webpage using BeautifulSoup."""
        try:
            response = requests.get(url, headers=self.headers, timeout=timeout)
            response.raise_for_status()
            
            # Use BeautifulSoup to extract main content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract title
            title = soup.title.string if soup.title else ""
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                element.decompose()
            
            # Extract text from main content areas (focusing on article, main, div with content)
            main_content = ""
            
            # Try to find main content in article tags
            articles = soup.find_all('article')
            if articles:
                for article in articles:
                    main_content += article.get_text(separator=' ', strip=True) + " "
            
            # If no article tags, try main tag
            if not main_content.strip():
                main_elements = soup.find_all('main')
                if main_elements:
                    for main in main_elements:
                        main_content += main.get_text(separator=' ', strip=True) + " "
            
            # If still no content, look for div with content-related classes/IDs
            if not main_content.strip():
                content_divs = soup.find_all('div', class_=lambda c: c and any(word in c.lower() 
                                            for word in ['content', 'article', 'post', 'entry', 'body', 'text']))
                if content_divs:
                    for div in content_divs:
                        main_content += div.get_text(separator=' ', strip=True) + " "
            
            # If still no content, get paragraphs from the body
            if not main_content.strip():
                paragraphs = soup.find_all('p')
                for p in paragraphs:
                    if len(p.get_text(strip=True)) > 50:  # Only substantial paragraphs
                        main_content += p.get_text(separator=' ', strip=True) + " "
            
            # If still no content, fall back to full body text
            if not main_content.strip():
                body = soup.body
                if body:
                    main_content = body.get_text(separator=' ', strip=True)
            
            # Basic text cleaning
            text = re.sub(r'\s+', ' ', main_content).strip()
            text = re.sub(r'[\n\r\t]', ' ', text)
            
            if title:
                text = f"{title}\n\n{text}"
                
            return text
        
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {str(e)}")
            return None
            
    def is_blocked(self, url: str, blocked_domains: List[str]) -> bool:
        """Check if a URL is from a blocked domain."""
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        return any(domain == blocked.lower() or domain.endswith('.' + blocked.lower()) for blocked in blocked_domains)
        
    def chunk_text(self, text: str, chunk_size: int = 200, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks of roughly equal size based on sentences."""
        # First split into paragraphs
        paragraphs = re.split(r'\n\s*\n', text)
        chunks = []
        
        # Simple sentence splitting
        sentences = []
        for paragraph in paragraphs:
            # Split paragraph into sentences (simple approach)
            para_sentences = re.split(r'(?<=[.!?])\s+', paragraph.strip())
            sentences.extend([s for s in para_sentences if s.strip()])
        
        # Group sentences into chunks with overlap
        current_chunk = []
        current_size = 0
        
        for sentence in sentences:
            sentence_words = len(sentence.split())
            
            if current_size + sentence_words <= chunk_size:
                current_chunk.append(sentence)
                current_size += sentence_words
            else:
                # Save current chunk if not empty
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                    
                # If overlap is specified, keep some sentences for next chunk
                if overlap > 0 and len(current_chunk) > 0:
                    # Calculate how many sentences to keep based on word count
                    overlap_size = 0
                    sentences_to_keep = []
                    
                    for s in reversed(current_chunk):
                        s_len = len(s.split())
                        if overlap_size + s_len <= overlap:
                            sentences_to_keep.insert(0, s)
                            overlap_size += s_len
                        else:
                            break
                            
                    # Start new chunk with overlapping sentences
                    current_chunk = sentences_to_keep
                    current_size = overlap_size
                else:
                    # No overlap, start fresh
                    current_chunk = []
                    current_size = 0
                
                # Add the current sentence to the new chunk
                current_chunk.append(sentence)
                current_size = sentence_words
        
        # Add the last chunk if not empty
        if current_chunk:
            chunks.append(' '.join(current_chunk))
            
        # If chunks are too small or empty, fallback to simpler chunking
        if not chunks or max(len(chunk.split()) for chunk in chunks) < 50:
            words = text.split()
            chunks = []
            for i in range(0, len(words), chunk_size - overlap):
                chunk = ' '.join(words[i:i + chunk_size])
                chunks.append(chunk)
                if i + chunk_size >= len(words):
                    break
        
        return chunks


class OptimizedVectorSearch:
    """Efficient vector similarity search without using FAISS."""
    
    @staticmethod
    def find_top_k_similar(query_embedding: np.ndarray, embeddings: np.ndarray, k: int = 10) -> Tuple[np.ndarray, np.ndarray]:
        """
        Find top-k most similar embeddings using cosine similarity.
        Returns (scores, indices) where both are numpy arrays of length k.
        """
        # Normalize query embedding (ensure it's a unit vector)
        query_embedding = query_embedding / np.linalg.norm(query_embedding, axis=1, keepdims=True)
        
        # For large embedding matrices, compute similarity in chunks to avoid memory issues
        chunk_size = 10000  # Adjust based on memory constraints
        n_vectors = embeddings.shape[0]
        scores = np.zeros(n_vectors)
        
        for i in range(0, n_vectors, chunk_size):
            end_idx = min(i + chunk_size, n_vectors)
            chunk_embeddings = embeddings[i:end_idx]
            
            # Calculate cosine similarity - this is just the dot product for normalized vectors
            chunk_scores = np.dot(query_embedding, chunk_embeddings.T)[0]
            scores[i:end_idx] = chunk_scores
        
        # Get top-k indices and scores
        if k >= n_vectors:
            top_k = n_vectors
        else:
            top_k = k
            
        top_indices = np.argpartition(scores, -top_k)[-top_k:]
        # Sort indices by score in descending order
        top_indices = top_indices[np.argsort(scores[top_indices])[::-1]]
        top_scores = scores[top_indices]
        
        return top_scores, top_indices


class WebSearchEngine:
    """Enhanced web search engine with advanced embedding and processing."""
    
    def __init__(self):
        """Initialize search engine components."""
        self.embedding_model = AdvancedEmbeddingModel()
        self.content_extractor = ContentExtractor()
        self.vector_search = OptimizedVectorSearch()
    
    def search(self, 
               query: str, 
               num_results: int = 100,
               blocked_domains: List[str] = None,
               output_file: str = "search_results.txt",
               chunks_file: str = "relevant_chunks.json",
               chunk_size: int = 500,
               overlap: int = 100,
               top_k: int = 20,
               max_parallel: int = 5) -> List[Dict[str, Any]]:
        """
        Perform a web search with advanced processing and ranking.
        
        Args:
            query: Search query
            num_results: Number of search results to fetch
            blocked_domains: List of domains to exclude
            output_file: File to save raw search results
            chunks_file: File to save processed chunks
            chunk_size: Size of content chunks in words
            overlap: Overlap between chunks in words
            top_k: Number of top chunks to return
            max_parallel: Maximum number of parallel scraping tasks
            
        Returns:
            List of relevant content chunks with metadata
        """
        if blocked_domains is None:
            blocked_domains = ["x.com", "twitter.com", "facebook.com", "instagram.com", "youtube.com", "tiktok.com", "reddit.com"]
        
        # Create data directory if it doesn't exist
        if not os.path.exists("data"):
            os.makedirs("data")
            logger.info("Created 'data' directory")
        
        # Create timestamped folder for this search
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        date_folder = datetime.now().strftime("%d_%m_%Y")
        search_folder = f"data/search_{date_folder}_{timestamp}"
        
        if not os.path.exists(search_folder):
            os.makedirs(search_folder)
            logger.info(f"Created search folder: {search_folder}")
        
        # Update output file paths to use the new folder
        output_file_path = os.path.join(search_folder, output_file)
        chunks_file_path = os.path.join(search_folder, chunks_file)
        
        # Log system information
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Current time (UTC): {current_time}")
        logger.info(f"User: gaurishmehra")
        
        # Perform web search
        logger.info(f"Searching for: {query}")
        start_time = time.time()
        with DDGS() as ddgs:
            search_results = list(ddgs.text(query, max_results=num_results))
        logger.info(f"Search completed in {time.time() - start_time:.2f}s, found {len(search_results)} results")
        
        # Extract and filter URLs
        urls = [result['href'] for result in search_results]
        titles = {result['href']: result.get('title', '') for result in search_results}
        filtered_urls = [url for url in urls if not self.content_extractor.is_blocked(url, blocked_domains)]
        logger.info(f"{len(filtered_urls)} URLs after filtering blocked domains")
        
        # Generate query embedding once
        query_embedding = self.embedding_model.get_query_embedding(query)
        
        # Scrape content in parallel
        all_chunks = []
        url_to_chunks = {}
        success_count = 0
        
        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            future_to_url = {executor.submit(self.content_extractor.extract_readable_content, url): url for url in filtered_urls}
            
            with open(output_file_path, 'w', encoding='utf-8') as f:
                for future in as_completed(future_to_url):
                    url = future_to_url[future]
                    try:
                        content = future.result()
                        if content and len(content) > 200:  # Ensure content is substantial
                            # Save raw content
                            f.write(f"URL: {url}\n")
                            f.write(f"TITLE: {titles.get(url, 'No Title')}\n")
                            f.write(f"CONTENT PREVIEW: {content[:500]}...\n\n")
                            f.write("-" * 80 + "\n\n")
                            
                            # Process content into chunks
                            chunks = self.content_extractor.chunk_text(content, chunk_size=chunk_size, overlap=overlap)
                            
                            # Store chunks with metadata
                            url_chunks = []
                            for chunk in chunks:
                                chunk_data = {
                                    "content": chunk,
                                    "url": url,
                                    "title": titles.get(url, "")
                                }
                                all_chunks.append(chunk_data)
                                url_chunks.append(chunk_data)
                            
                            url_to_chunks[url] = url_chunks
                            success_count += 1
                            logger.info(f"Successfully processed {url} - {len(chunks)} chunks extracted")
                    
                    except Exception as e:
                        logger.error(f"Error processing {url}: {str(e)}")
        
        if not all_chunks:
            logger.error("No content was successfully scraped")
            return []
            
        logger.info(f"Successfully extracted content from {success_count} pages, total chunks: {len(all_chunks)}")
        
        # Create embeddings for all chunks
        logger.info("Generating embeddings for chunks...")
        start_time = time.time()
        chunk_texts = [chunk["content"] for chunk in all_chunks]
        chunk_embeddings = self.embedding_model.get_embeddings(chunk_texts)
        logger.info(f"Embedding generation completed in {time.time() - start_time:.2f}s")
        
        # Find most similar chunks using numpy-based similarity search
        logger.info("Finding most similar chunks...")
        start_time = time.time()
        top_scores, top_indices = self.vector_search.find_top_k_similar(
            query_embedding, 
            chunk_embeddings, 
            k=min(top_k, len(all_chunks))
        )
        logger.info(f"Similarity search completed in {time.time() - start_time:.2f}s")
        
        # Prepare ranked results
        relevant_chunks = []
        for rank, (score, idx) in enumerate(zip(top_scores, top_indices)):
            chunk_data = all_chunks[idx]
            result = {
                "rank": rank + 1,
                "similarity_score": float(score),
                "source_url": chunk_data["url"],
                "title": chunk_data["title"],
                "chunk": chunk_data["content"]
            }
            relevant_chunks.append(result)
        
        # Save results as JSON
        with open(chunks_file_path, 'w', encoding='utf-8') as f:
            json.dump(relevant_chunks, f, indent=2)
        
        # Save text version for easy reading
        text_output_file = os.path.join(search_folder, "relevant_chunks.txt")
        with open(text_output_file, 'w', encoding='utf-8') as f:
            f.write(f"Search query: {query}\n")
            f.write(f"Generated on: {current_time}\n")
            f.write(f"User: gaurishmehra\n\n")
            
            for chunk_data in relevant_chunks:
                f.write(f"RANK {chunk_data['rank']} (Score: {chunk_data['similarity_score']:.4f})\n")
                f.write(f"TITLE: {chunk_data['title']}\n")
                f.write(f"URL: {chunk_data['source_url']}\n")
                f.write(f"CONTENT:\n{chunk_data['chunk']}\n")
                f.write("=" * 80 + "\n\n")
        
        logger.info(f"Saved {len(relevant_chunks)} ranked chunks to {chunks_file_path} and {text_output_file}")
        logger.info(f"All results saved in folder: {search_folder}")
        return relevant_chunks


def search(query, num_results=100, blocked_domains=None, output_file="search_results.txt", 
           chunks_file="relevant_chunks.json", chunk_size=500, overlap=0, top_k=50):
    """
    Main search function - improved version with advanced processing.
    """
    search_engine = WebSearchEngine()
    return search_engine.search(
        query=query, 
        num_results=num_results,
        blocked_domains=blocked_domains,
        output_file=output_file,
        chunks_file=chunks_file,
        chunk_size=chunk_size,
        overlap=overlap,
        top_k=top_k
    )