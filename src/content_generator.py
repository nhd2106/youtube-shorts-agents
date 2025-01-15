from typing import TypedDict, List, Dict, Any, Optional
from openai import AsyncOpenAI
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import io
from PIL import Image
import uuid
import os
import json

class VideoFormat(TypedDict):
    type: str  # 'shorts' or 'normal'
    duration: str  # '60s' for shorts, 'flexible' for normal

class Content(TypedDict):
    script: str
    title: str
    hashtags: list[str]
    format: VideoFormat
    image_urls: list[str]  # Add this field for storing extracted image URLs

class ContentGenerator:
    def __init__(self):
        self.client = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'cross-site'
        }

    def _init_client(self, api_keys: dict):
        """Initialize OpenAI client with API key"""
        if not api_keys.get('openai'):
            raise ValueError("OpenAI API key is required")
        self.client = AsyncOpenAI(api_key=api_keys['openai'])
        # Initialize Together AI
        if not api_keys.get('together'):
            raise ValueError("Together AI API key is required for image generation")
        import together
        together.api_key = api_keys['together']
        self.together_client = together

    async def _extract_images_from_url(self, url: str) -> List[str]:
        """Extract image URLs from a webpage, focusing on main content area"""
        try:
            # Disable SSL verification warnings
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # Create a session with SSL verification disabled
            session = requests.Session()
            session.verify = False
            
            # Add retry mechanism
            retries = urllib3.util.Retry(
                total=3,
                backoff_factor=0.5,
                status_forcelist=[500, 502, 503, 504]
            )
            session.mount('https://', requests.adapters.HTTPAdapter(max_retries=retries))
            
            response = session.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            image_urls = set()  # Use set to avoid duplicates
            
            # First, try to find the main content area with specific site patterns
            content_selectors = [
                'div.article-body',          # dantri.com.vn
                'div.dt-news__content',      # dantri.com.vn (alternate)
                'article',                   # general
                'main',                      # general
                'div.content-detail',        # general news sites
                'div.article-content',       # general news sites
                'div.post-content',          # blog style
                'div.entry-content',         # wordpress
                'div.main-content',          # general
                'div.container',             # common container class
                'div.main',                  # main content class
                'div.main-container',        # combined main container
                'div.content-container',     # content container
                'div.article-container',     # article container
                'div.post-container'         # post container
            ]
            
            main_content = None
            
            # First try to find sections containing h1 or h2 tags
            for heading in soup.find_all(['h1', 'h2']):
                # Look for parent containers that might be the main content
                parent = heading.find_parent(['article', 'main', 'div'])
                if parent:
                    # Check if parent has relevant classes
                    parent_classes = parent.get('class', [])
                    relevant_classes = any(cls in ' '.join(parent_classes).lower() 
                                        for cls in ['content', 'article', 'post', 'main', 'container'])
                    
                    # Check if this parent contains substantial content
                    text_length = len(parent.get_text())
                    images_count = len(parent.find_all('img'))
                    paragraphs_count = len(parent.find_all('p'))
                    
                    if (text_length > 500 or images_count > 0 or paragraphs_count > 2) and \
                       (relevant_classes or text_length > 1000):  # More strict if no relevant classes
                        main_content = parent
                        print(f"Found content area containing heading: {heading.get_text()[:50]}...")
                        break

            # If no content found with headings, try regular selectors
            if not main_content:
                for selector in content_selectors:
                    if '.' in selector:
                        # Class selector
                        class_name = selector.split('.')[-1]
                        main_content = soup.find('div', class_=class_name)
                    else:
                        # Tag selector
                        main_content = soup.find(selector)
                    if main_content:
                        print(f"Found content area using selector: {selector}")
                        break
            
            if not main_content:
                # Fallback: try to find any div with content-related classes
                content_patterns = [
                    r'article|post|entry|content|body|detail|main|text|container',
                ]
                for pattern in content_patterns:
                    candidates = soup.find_all('div', class_=re.compile(pattern, re.I))
                    # Sort candidates by content length to find the most substantial one
                    candidates = sorted(candidates, 
                                     key=lambda x: len(x.get_text()) + len(x.find_all('img')) * 100,
                                     reverse=True)
                    if candidates:
                        main_content = candidates[0]
                        print(f"Found content area using pattern: {pattern}")
                        break
            
            if main_content:
                # Find all figures first (often contain main article images)
                for figure in main_content.find_all('figure'):
                    img = figure.find('img')
                    if img:
                        for attr in ['data-original', 'data-src', 'src']:
                            src = img.get(attr)
                            if src:
                                src = self._clean_url(src, url)
                                if self._is_valid_image_url(src):
                                    image_urls.add(src)
                                    print(f"Found image in figure: {src}")
                                    break
                
                # Then find all images
                for img in main_content.find_all('img'):
                    for attr in ['data-original', 'data-src', 'src']:
                        src = img.get(attr)
                        if src:
                            src = self._clean_url(src, url)
                            if self._is_valid_image_url(src):
                                image_urls.add(src)
                                print(f"Found image: {src}")
                                break
            
            # If we still don't have enough images, try meta og:image
            if len(image_urls) < 3:
                for meta in soup.find_all('meta', property=['og:image', 'twitter:image']):
                    content = meta.get('content')
                    if content:
                        src = self._clean_url(content, url)
                        if self._is_valid_image_url(src):
                            image_urls.add(src)
                            print(f"Found meta image: {src}")
            
            # If still not enough images, look for images near headings
            if len(image_urls) < 3:
                for heading in soup.find_all(['h1', 'h2', 'h3']):
                    # Look for images in siblings
                    for sibling in heading.find_next_siblings():
                        for img in sibling.find_all('img'):
                            for attr in ['data-original', 'data-src', 'src']:
                                src = img.get(attr)
                                if src:
                                    src = self._clean_url(src, url)
                                    if self._is_valid_image_url(src):
                                        image_urls.add(src)
                                        print(f"Found image near heading: {src}")
                                        break
                        if len(image_urls) >= 3:
                            break
                    if len(image_urls) >= 3:
                        break
            
            print(f"Found {len(image_urls)} images from main content area of {url}")
            return list(image_urls)
            
        except requests.exceptions.SSLError as ssl_err:
            print(f"SSL Error for {url}: {str(ssl_err)}")
            return []
        except Exception as e:
            print(f"Error extracting images from URL: {str(e)}")
            return []

    def _clean_url(self, url: str, base_url: str) -> str:
        """Clean and normalize image URL"""
        if not url:
            return ""
            
        # Handle protocol-relative URLs
        if url.startswith('//'):
            return 'https:' + url
            
        # Handle relative URLs
        if not url.startswith(('http://', 'https://')):
            return urljoin(base_url, url)
            
        return url

    def _is_valid_image_url(self, url: str) -> bool:
        """Check if URL points to a valid image"""
        try:
            # List of common image extensions
            image_extensions = ('.jpg', '.jpeg', '.png', '.webp')
            
            # Exclude patterns (reduced to focus on size-related patterns)
            excluded_patterns = (
                'icon',
                'avatar',
                'emoji',
                'button',
                'logo-small',
            )
            
            url_lower = url.lower()
            
            # Basic checks
            if not url_lower or 'data:image' in url_lower:
                return False
                
            # Check file extension
            if not any(url_lower.endswith(ext) for ext in image_extensions):
                return False
                
            # Check for excluded patterns
            if any(pattern in url_lower for pattern in excluded_patterns):
                return False
            
            # Check for dimensions in URL (if present)
            dimensions = re.findall(r'(\d+)x(\d+)', url_lower)
            if dimensions:
                width, height = map(int, dimensions[0])
                if width < 300 or height < 300:  # Reduced minimum size
                    return False
            
            # Check for small image indicators in URL
            small_indicators = ['thumb', 'tiny', '150x', '100x', '200x']
            if any(indicator in url_lower for indicator in small_indicators):
                return False
            
            return True
            
        except Exception as e:
            print(f"Error validating image URL {url}: {str(e)}")
            return False

    def _extract_images_from_json(self, data: Any, image_urls: set, base_url: str):
        """Recursively extract image URLs from JSON-LD data"""
        if isinstance(data, dict):
            for key, value in data.items():
                if key in ['image', 'thumbnail', 'contentUrl'] and isinstance(value, str):
                    absolute_url = urljoin(base_url, value)
                    if self._is_valid_image_url(absolute_url):
                        image_urls.add(absolute_url)
                else:
                    self._extract_images_from_json(value, image_urls, base_url)
        elif isinstance(data, list):
            for item in data:
                self._extract_images_from_json(item, image_urls, base_url)

    async def _extract_content_from_url(self, url: str) -> Dict[str, Any]:
        """Extract content and images from a URL"""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract title
            title = soup.title.string if soup.title else ""
            
            # Extract main content (focusing on article or main content areas)
            content = ""
            main_content = soup.find('article') or soup.find('main') or soup.find('div', class_=re.compile(r'content|article|post'))
            if main_content:
                # Remove script and style elements
                for element in main_content(['script', 'style']):
                    element.decompose()
                content = main_content.get_text(separator='\n').strip()
            
            # Extract images
            image_urls = await self._extract_images_from_url(url)
            
            return {
                'title': title,
                'content': content,
                'image_urls': image_urls
            }
            
        except Exception as e:
            print(f"Error extracting content from URL: {str(e)}")
            return {'title': '', 'content': '', 'image_urls': []}

    async def generate_content(self, idea: str, video_format: str = "shorts", api_keys: dict = None) -> Content:
        try:
            if not api_keys:
                raise ValueError("API keys are required")
            
            # Check if idea contains a URL
            url_pattern = re.compile(
                r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
            )
            urls = url_pattern.findall(idea)
            
            extracted_content = None
            image_urls = []
            
            if urls:
                print(f"Found URL in idea: {urls[0]}")
                # Extract content and images from the first URL
                extracted_content = await self._extract_content_from_url(urls[0])
                image_urls = extracted_content['image_urls']
                print(f"Extracted {len(image_urls)} images from URL")
                
                # Update idea with extracted content
                if extracted_content['content']:
                    idea = f"{idea}\n\nExtracted content:\n{extracted_content['content']}"
            
            # Initialize OpenAI client with API key
            self._init_client(api_keys)

            # Define format specifications
            format_specs = {
                "shorts": {
                    "type": "shorts",
                    "duration": "70s",
                    "script_length": "70 - 85 seconds",
                    "style": "energetic and engaging",
                    "word_count": "250-300 words"
                },
                "normal": {
                    "type": "normal",
                    "duration": "flexible",
                    "script_length": "8-10 minutes",
                    "style": "detailed and comprehensive",
                    "word_count": "2500 - 3000 words"
                }
            }

            if video_format not in format_specs:
                raise ValueError(f"Invalid video format. Choose from: {list(format_specs.keys())}")

            format_spec = format_specs[video_format]

            # Update system prompt based on video format
            system_prompt = f'''You are a creative content specialist focused on creating engaging {video_format} videos.
You must respond in this exact format:
TITLE: [attention-grabbing title]
SCRIPT: [engaging script]
HASHTAGS: [relevant hashtags]

Guidelines for content creation:
1. Title Creation:
    - Ensure the title language matches the user input
    - Craft an attention-grabbing, unique title that sparks curiosity
    - Use relevant keywords for better discoverability
    - Keep it clear, concise, and compelling
    - Avoid clickbait - ensure the title accurately reflects content

2. Script rules:
    - Content Type Guidelines:
        • Historical: Include vivid storytelling elements to make dates and locations more engaging
        • Narrative: Focus on building relatable characters and a compelling plot
        • Factual: Use intriguing hooks to capture attention early on
        • Tutorial: Include interactive elements or visuals to aid understanding
        • Opinion: Balance opinions with compelling arguments and counterpoints to stimulate thought
    - Reference Guidelines:
        • when user paste url, you need Extract detailed information from the following article, including specific numbers, times, and key events:
            1. The main topic or purpose of the content.
            2. Key details, including dates, numbers, or statistics mentioned.
            3. Specific events, incidents, or actions described, if applicable.
            4. Any insights, arguments, or conclusions presented by the author.
            5. Notable quotes or statements from the text.
            6. Other relevant details that contribute to understanding the content.
            Provide a clear and concise summary of the extracted information, structured for readability.
        • Encourage the use of visuals or infographics when extracting detailed information
        • Summarize key points in bullet form for easier readability and retention
    - Content Requirements:
        • Consistently match the input language
        • don't seperate numbers by comma or dot, keep them together
        • Focus solely on the requested topic
        • Target length: {format_spec["word_count"]} for a {format_spec["script_length"]} video
        • Keep the tone {format_spec["style"]}
        • Maintain a consistent tone that aligns with the intended audience
        • Use storytelling techniques such as anecdotes or metaphors
        • For normal format: Include detailed examples, case studies, or real-world applications
        • For shorts: Keep it concise and immediately engaging, use punchy language and dynamic visuals
        • Conclude with: in English "If you found this helpful, like and subscribe for more!"  or in Vietnamese "Nếu bạn thấy hay, đừng quên bấm like và đăng ký để ủng hộ kênh" (Choose one based on the user input language)
    - Storytelling Framework - Select ONE:
        • Hero's Journey: Challenge → Struggle → Triumph
        • 7-Second Hook: Grab attention in the first 7 seconds
        • Problem-Solution-Benefit Structure
        • 5-Why Analysis: Deep dive into root causes
        • Dual-Perspective Story: Before/After format
        • 10-Second Engagement Rule
        • Rhythmic/Rhyming Pattern for memorability
        • Experiment with different frameworks to see which resonates best
        • Use the 7-Second Hook to grab attention immediately
    * Remember: Language must match with the user input language

3. Hashtag Strategy:
    - Blend English and topic-specific hashtags
    - Include trending, relevant tags
    - Ensure hashtag relevance to content
    - Optimal mix: 60% topic-specific, 40% general engagement
    - Regularly update hashtags to include trending topics
    - Analyze engagement metrics to refine hashtag usage

4. Quality Standards:
    - Prioritize accuracy and current information
    - Maintain educational or entertainment value
    - Focus on audience engagement and value delivery
    - Keep content concise and impactful
    - Avoid filler content or unnecessary details
    - For normal format: Include supporting details, examples, and deeper analysis
    - For shorts: Focus on key points and immediate value
    - Incorporate user feedback to improve content quality
    - Use analytics to identify best-performing content formats and topics

Note: Exclude emojis, icons, or special characters from the script content.'''

            # Make the API call
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # or "gpt-3.5-turbo" for lower cost
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Create a {video_format} video script about: {idea}"}
                ],
                temperature=0.7,
            )
            
            # Get the content
            content = response.choices[0].message.content
            print("\nDebug - Raw API Response:")
            print(content)
            
            # Parse the content
            parsed_content = self._parse_content(content, format_spec)
            
            # Add extracted image URLs to the content
            if image_urls:
                parsed_content["image_urls"] = image_urls
            
            return parsed_content
            
        except Exception as e:
            print(f"\nDebug - Error details: {str(e)}")
            raise

    def _parse_content(self, content: str, format_spec: dict) -> Content:
        """Helper method to parse the assistant's response"""
        title = ""
        script = ""
        hashtags = []
        current_section = None
        
        # Parse response line by line
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('TITLE:'):
                current_section = 'title'
                title = line.replace('TITLE:', '').strip()
            elif line.startswith('SCRIPT:'):
                current_section = 'script'
                script = line.replace('SCRIPT:', '').strip()
            elif line.startswith('HASHTAGS:'):
                current_section = 'hashtags'
                hashtags_str = line.replace('HASHTAGS:', '').strip()
                hashtags = [tag.strip() for tag in hashtags_str.split(',')]
            elif current_section == 'script':
                # Append to script if we're in script section
                script += '\n' + line
        
        # Validate content
        if not title or not script or not hashtags:
            print("\nDebug - Parsed Content:")
            print(f"Title: {title}")
            print(f"Script: {script}")
            print(f"Hashtags: {hashtags}")
            raise ValueError("Some content sections are missing")
        
        return {
            "title": title,
            "script": script,
            "hashtags": hashtags,
            "format": {
                "type": format_spec["type"],
                "duration": format_spec["duration"]
            },
            "image_urls": []
        }

    async def download_and_process_image(self, url: str, output_dir: str) -> Optional[str]:
        """Download and process an image from a URL"""
        try:
            import httpx
            
            # Create httpx client with SSL verification disabled
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                response = await client.get(url, headers=self.headers, follow_redirects=True)
                if response.status_code != 200:
                    print(f"Failed to download image: HTTP {response.status_code}")
                    return None
                
                image_data = response.content
                print(f"Successfully downloaded image: {url}")

            # Process image with PIL
            try:
                image = Image.open(io.BytesIO(image_data))
                
                # Convert to RGB if necessary
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                # Get original dimensions for logging
                original_size = image.size
                
                # Check if image is too small
                if original_size[0] < 300 or original_size[1] < 300:
                    print(f"Image too small: {original_size}")
                    return None
                
                # Resize and crop to match video dimensions
                resized_image = self._resize_and_crop(image)
                
                # Generate unique filename
                filename = f"{uuid.uuid4()}.jpg"
                output_path = os.path.join(output_dir, filename)
                
                # Save processed image
                resized_image.save(output_path, 'JPEG', quality=95)
                
                print(f"Successfully processed image: {url}")
                print(f"Original size: {original_size}, Resized to: {resized_image.size}")
                return output_path
                
            except Exception as e:
                print(f"Error processing image data: {str(e)}")
                return None
                
        except Exception as e:
            print(f"Error downloading image from {url}: {str(e)}")
            return None

    def _resize_and_crop(self, image: Image.Image) -> Image.Image:
        """Resize and crop image to match video dimensions while maintaining aspect ratio"""
        if not hasattr(self, 'WIDTH') or not hasattr(self, 'HEIGHT'):
            raise ValueError("Video dimensions not set. Call set_format() first.")
            
        # Calculate target aspect ratio
        target_ratio = self.WIDTH / self.HEIGHT
        
        # Get current image dimensions
        width, height = image.size
        current_ratio = width / height
        
        if current_ratio > target_ratio:
            # Image is wider than needed
            new_width = int(height * target_ratio)
            left = (width - new_width) // 2
            image = image.crop((left, 0, left + new_width, height))
        else:
            # Image is taller than needed
            new_height = int(width / target_ratio)
            top = (height - new_height) // 2
            image = image.crop((0, top, width, top + new_height))
        
        # Resize to target dimensions using Lanczos resampling
        return image.resize((self.WIDTH, self.HEIGHT), Image.Resampling.LANCZOS)