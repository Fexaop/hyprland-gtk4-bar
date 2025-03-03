import time
import re
import requests
import logging
import json
import os
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from duckduckgo_search import DDGS
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from openai import OpenAI

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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


class LLMProcessor:
    """Class for interacting with Large Language Models."""
    
    def __init__(self, api_key=None, base_url=None):
        """Initialize LLM processor."""
        self.api_key = api_key or "csk-pd3m4cwpk3pppkkv3vtnxwnnv92kf5txctek86ff3j66xwf2"
        self.base_url = base_url or "https://api.cerebras.ai/v1"
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
    
    def generate_sub_questions(self, query: str) -> List[str]:
        """
        Generate sub-questions to decompose a complex query.
        
        Args:
            query: The original search query
            
        Returns:
            List of sub-questions to be researched
        """
        system_prompt = """You are a research assistant that decomposes complex questions into specific sub-questions.
        Your task is to break down the main research query into 3-7 specific questions that together will provide a comprehensive answer.
        Return your response as a JSON array of questions only."""
        
        user_message = f"""
        I need to research the following topic: "{query}"
        
        Please break this down into specific research questions that would help me gather comprehensive information.
        Each question should focus on a different aspect of the topic.
        Return ONLY a JSON array with the questions, like this: ["Question 1", "Question 2", "Question 3"].
        Do not include any explanations or other text outside the JSON format.
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b",
                messages=messages,
                temperature=0.75,
                max_tokens=2048,
            )
            
            result = response.choices[0].message.content.strip()
            
            # Extract JSON array from response if needed
            if "```json" in result:
                json_text = result.split("```json")[1].split("```")[0].strip()
                questions = json.loads(json_text)
            elif result.startswith('[') and result.endswith(']'):
                questions = json.loads(result)
            else:
                # Try to extract JSON from text
                match = re.search(r'\[.*\]', result, re.DOTALL)
                if match:
                    questions = json.loads(match.group(0))
                else:
                    logger.error(f"Could not parse response as JSON: {result}")
                    # Fallback: split by newlines and clean up
                    lines = [line.strip() for line in result.split('\n') if line.strip()]
                    questions = [line.strip('"').strip() for line in lines if line.strip()]
            
            logger.info(f"Generated {len(questions)} sub-questions")
            return questions
        
        except Exception as e:
            logger.error(f"Error generating sub-questions: {str(e)}")
            # Return a single question (the original query) as fallback
            return [query]
    
    def summarize_page(self, page_content: str, url: str, title: str, sub_question: str) -> Dict[str, Any]:
        """
        Process webpage content to generate a summary relevant to the sub-question.
        
        Args:
            page_content: The extracted content from the webpage
            url: The URL of the webpage
            title: The title of the webpage
            sub_question: The specific sub-question being researched
            
        Returns:
            Dictionary containing the summary and metadata
        """
        system_prompt = "You are a helpful assistant that summarizes webpage content accurately and concisely."
        
        user_message = f"""
        Please summarize the following webpage content in relation to this specific research question: "{sub_question}"
        
        URL: {url}
        Title: {title}
        
        Content:
        {page_content[:16000]}
        
        Your summary should:
        1. Focus on information relevant to the research question
        2. Extract key facts, data points, and insights
        3. Be clear and as detailed as possible
        4. Maintain factual accuracy
        5. Note any limitations or gaps in the information
        6. Do not mention phrases like "based on xyz" or anything like that, return only and only the highly detailed summary, failing to do so will be considered as an incorrect response.
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b",
                messages=messages,
                temperature=0.5,
                max_tokens=16000,
            )
            
            summary = response.choices[0].message.content
            
            return {
                "url": url,
                "title": title,
                "sub_question": sub_question,
                "content_length": len(page_content),
                "summary": summary,
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Error summarizing page: {str(e)}")
            return {
                "url": url,
                "title": title,
                "sub_question": sub_question,
                "content_length": len(page_content),
                "summary": f"Error generating summary: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
    
    def generate_comprehensive_report(self, query: str, all_summaries: List[Dict[str, Any]]) -> str:
        """
        Generate a comprehensive report by combining all the page summaries.
        
        Args:
            query: The original research query
            all_summaries: List of all page summaries organized by sub-question
            
        Returns:
            A comprehensive report combining all summaries
        """
        # Organize summaries by sub-question
        summaries_by_question = {}
        for summary in all_summaries:
            question = summary["sub_question"]
            if question not in summaries_by_question:
                summaries_by_question[question] = []
            summaries_by_question[question].append(summary)
        
        # Create the combined report
        report = f"# Comprehensive Research Report\n\n"
        report += f"## Summary\nThis report combines research from {len(all_summaries)} sources " \
                f"across {len(summaries_by_question)} research questions.\n\n"
        
        # Add each sub-question and its summaries
        for question, summaries in summaries_by_question.items():
            report += f"## {question}\n\n"
            
            for i, summary in enumerate(summaries, 1):
                report += f"### Source {i}: {summary['title']}\n"
                report += f"URL: {summary['url']}\n\n"
                report += f"{summary['summary']}\n\n"
                report += "---\n\n"
        
        # Add timestamp
        report += f"\n\nReport generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return report


class WebSearchEngine:
    """Web search engine with question decomposition and LLM-based summarization."""
    
    def __init__(self, api_key=None, base_url=None):
        """Initialize search engine components."""
        self.content_extractor = ContentExtractor()
        self.llm_processor = LLMProcessor(api_key, base_url)
    
    def search_for_sub_question(self, 
                               sub_question: str,
                               num_results: int = 7,
                               blocked_domains: List[str] = None,
                               max_parallel: int = 5) -> List[Dict[str, Any]]:
        """
        Search and scrape content for a specific sub-question.
        
        Args:
            sub_question: The specific question to research
            num_results: Number of search results to fetch
            blocked_domains: List of domains to exclude
            max_parallel: Maximum number of parallel scraping tasks
            
        Returns:
            List of page summaries for this sub-question
        """
        if blocked_domains is None:
            blocked_domains = ["x.com", "twitter.com", "facebook.com", "instagram.com", "youtube.com", "tiktok.com", "reddit.com"]
        
        logger.info(f"Searching for sub-question: {sub_question}")
        start_time = time.time()
        
        # Perform web search
        try:
            with DDGS() as ddgs:
                search_results = list(ddgs.text(sub_question, max_results=num_results))
            logger.info(f"Search completed in {time.time() - start_time:.2f}s, found {len(search_results)} results")
        except Exception as e:
            logger.error(f"Error during search: {str(e)}")
            return []
        
        # Extract and filter URLs
        urls = [result['href'] for result in search_results]
        titles = {result['href']: result.get('title', '') for result in search_results}
        filtered_urls = [url for url in urls if not self.content_extractor.is_blocked(url, blocked_domains)]
        
        if not filtered_urls:
            logger.warning(f"No valid URLs found for sub-question: {sub_question}")
            return []
        
        logger.info(f"{len(filtered_urls)} URLs after filtering blocked domains")
        
        # Scrape content in parallel
        scraped_pages = []
        
        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            future_to_url = {executor.submit(self.content_extractor.extract_readable_content, url): url for url in filtered_urls}
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    content = future.result()
                    if content and len(content) > 200:  # Ensure content is substantial
                        # Store page info for processing
                        scraped_pages.append({
                            "url": url,
                            "title": titles.get(url, "No Title"),
                            "content": content,
                            "sub_question": sub_question
                        })
                        logger.info(f"Successfully scraped content from {url}")
                
                except Exception as e:
                    logger.error(f"Error processing {url}: {str(e)}")
        
        if not scraped_pages:
            logger.error(f"No content was successfully scraped for sub-question: {sub_question}")
            return []
        
        # Process each page with LLM to generate summaries
        page_summaries = []
        for page in scraped_pages:
            summary = self.llm_processor.summarize_page(
                page_content=page["content"],
                url=page["url"],
                title=page["title"],
                sub_question=sub_question
            )
            page_summaries.append(summary)
        
        logger.info(f"Generated {len(page_summaries)} summaries for sub-question: {sub_question}")
        return page_summaries
    
    def search(self, 
               query: str,
               sites_per_question: int = 7,
               blocked_domains: List[str] = None) -> Dict[str, Any]:
        """
        Perform a complete search process:
        1. Decompose query into sub-questions
        2. Search each sub-question
        3. Compile and synthesize results
        
        Args:
            query: The main search query
            sites_per_question: Number of sites to search per sub-question
            blocked_domains: List of domains to exclude
            
        Returns:
            Dictionary with the comprehensive report and search metadata
        """
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
        
        # Create reports directory if it doesn't exist
        if not os.path.exists("reports"):
            os.makedirs("reports")
            logger.info("Created 'reports' directory")
        
        # Log search information
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Current time (UTC): {current_time}")
        logger.info(f"Main search query: {query}")
        
        # Step 1: Generate sub-questions using LLM
        sub_questions = self.llm_processor.generate_sub_questions(query)
        
        # Save sub-questions to file
        questions_file = os.path.join(search_folder, "sub_questions.json")
        with open(questions_file, 'w', encoding='utf-8') as f:
            json.dump(sub_questions, f, indent=2)
        logger.info(f"Saved {len(sub_questions)} sub-questions to {questions_file}")
        
        # Step 2: Search each sub-question
        all_summaries = []
        
        for i, sub_question in enumerate(sub_questions, 1):
            logger.info(f"Processing sub-question {i}/{len(sub_questions)}: {sub_question}")
            
            # Create sub-folder for this question
            question_folder = os.path.join(search_folder, f"question_{i}")
            if not os.path.exists(question_folder):
                os.makedirs(question_folder)
            
            # Search and summarize for this sub-question
            summaries = self.search_for_sub_question(
                sub_question=sub_question,
                num_results=sites_per_question,
                blocked_domains=blocked_domains
            )
            
            # Save summaries for this question
            if summaries:
                question_summaries_file = os.path.join(question_folder, "summaries.json")
                with open(question_summaries_file, 'w', encoding='utf-8') as f:
                    json.dump(summaries, f, indent=2)
                
                all_summaries.extend(summaries)
            
            # Delay between sub-questions to respect rate limits
            if i < len(sub_questions):
                logger.info("Pausing before next sub-question...")
                time.sleep(5)
        
        # Save all summaries
        all_summaries_file = os.path.join(search_folder, "all_summaries.json")
        with open(all_summaries_file, 'w', encoding='utf-8') as f:
            json.dump(all_summaries, f, indent=2)
        
        # Step 3: Generate comprehensive report
        logger.info("Generating comprehensive report...")
        report = self.llm_processor.generate_comprehensive_report(query, all_summaries)
        
        # Save report to data folder (original location)
        report_file = os.path.join(search_folder, "comprehensive_report.md")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        # Also save report to reports folder with new filename format
        report_timestamp = datetime.now().strftime("%H:%M-%d/%m/%Y")
        report_file_new = os.path.join("reports", f"{report_timestamp}.md")
        
        # Make sure any nested directory in the path exists
        os.makedirs(os.path.dirname(report_file_new), exist_ok=True)
        
        with open(report_file_new, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"Saved comprehensive report to {report_file}")
        logger.info(f"Also saved report to {report_file_new}")
        
        # Prepare results
        result = {
            "query": query,
            "sub_questions": sub_questions,
            "summary_count": len(all_summaries),
            "report": report,
            "timestamp": current_time,
            "output_folder": search_folder,
            "report_file": report_file_new
        }
        
        return result


def search(query, sites_per_question=7, blocked_domains=None):
    """
    Main search function - query decomposition, web search with LLM-based summarization, and synthesis.
    
    Args:
        query: The main search query
        sites_per_question: Number of sites to search per sub-question
        blocked_domains: List of domains to exclude
        
    Returns:
        Dictionary with comprehensive report and search metadata
    """
    search_engine = WebSearchEngine()
    return search_engine.search(
        query=query,
        sites_per_question=sites_per_question,
        blocked_domains=blocked_domains
    )