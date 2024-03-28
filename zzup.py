from concurrent.futures import ThreadPoolExecutor
import os
import urllib.request, urllib.parse
import requests
import argparse
from tqdm import tqdm
from time import time

# Clean a directory name by removing illegal characters.
def clean_dirname(name: str) -> str:
    name = name.strip()
    illegal_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in illegal_chars:
        name = name.replace(char, '')
    return name

# Download a file from a URL.
def dl(args: tuple):
    url, name = args
    if not os.path.exists(name):  # Check if the file already exists
        try:
            response = requests.get(url, allow_redirects=True)
            response.raise_for_status()  # Raises a HTTPError for bad responses
            with open(name, "wb") as file:
                file.write(response.content)
        except requests.exceptions.RequestException as e:
            print(f"Error downloading {url}: {e}")
        except IOError as e:
            print(f"Error writing {name}: {e}")
    else:
        print(f"File {name} already exists, skipping download.")

def download_collection(url: str, num_processes: int, output_dir: str) -> None:
    url_base = '/'.join(url.split("/")[:-1])
    url = url_base + "/index.html"
    dir_name = clean_dirname(url.split("/")[-2])  # Assuming the collection name is the second last part of the URL
    collection_dir = os.path.join(output_dir, dir_name) # Create a directory with the collection name
    os.makedirs(collection_dir, exist_ok=True) # Create the directory to save the images

    collection_page = scrape(url) # Get the HTML of the collection page
    num_pages = int(collection_page.split("1 / ")[1].split(" ")[0]) # Get the number of pages in the collection
    print(num_pages) 

    # Loop through each page in the collection
    for i in range(1, num_pages + 1):
        page_url = url_base + f"/page-{i}.html"
        collection_page = scrape(page_url) # Get the HTML of the page
        collection_list = collection_page.split("<a target=\"_blank\" href=\"/content/")

        # Loop through each gallery on the page
        for j in range(1, len(collection_list)):
            gallery_page_url = "https://zzup.com/content/" + collection_list[j].split("\"")[0]
            download_gallery(gallery_page_url, num_processes, output_dir)

#  Download a gallery from a URL.
def download_gallery(url: str, num_processes: int, output_dir: str) -> None:
    url = '/'.join(url.split("/")[:-1]) + "/index.html"
    gallery_page = scrape(url)
    gallery_name = gallery_page.split("<span style=\"font-weight: bold;font-size: 30px;\">")[1].split("<")[0]
    gallery_name = clean_dirname(gallery_name)
    total_dir = os.path.join(output_dir, gallery_name)

    os.makedirs(total_dir, exist_ok=True) # Create the directory to save the images

    image_page_url = "https://zzup.com/viewimage/" + gallery_page.split("href=\"/viewimage/")[1].split("\"")[0]
    image_page = scrape(image_page_url)
    num_images = int(image_page.split("1 | ")[1].split(" ")[0])
    image_url = "https://zzup.com/" + image_page.split("<a href=\"/")[1].split("\"")[0]

    print(f"Downloading gallery: \"{gallery_name}\" - {num_images} images")
    # Create a list of tuples with the image URLs and filenames
    params = [(image_url.replace("image00001", f"image{str(i).zfill(5)}"), os.path.join(total_dir, f"{str(i).zfill(4)}.jpg")) for i in range(1, num_images + 1)]

    # Download the images using multiple threads
    with ThreadPoolExecutor(max_workers=num_processes) as executor:
        futures = [executor.submit(dl, param) for param in params] # Start the download threads
        
        # Display a progress bar
        with tqdm(total=num_images, desc="Downloading", unit="files") as pbar:
            # iterate over the futures as they complete
            for future in futures:
                future.result()  # Wait for each download to complete
                pbar.update() # Increment the progress bar
                
# Scrape a URL and return the HTML.
def scrape(url: str, data: dict = None) -> str:
    # Send a GET request to the URL
    if data is not None:
        data = urllib.parse.urlencode(data).encode()
    user_agent = "Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.7) Gecko/2009021910 Firefox/3.0.7"
    headers = {"User-Agent": user_agent}
    request = urllib.request.Request(url, data, headers)
    response = urllib.request.urlopen(request)
    return response.read().decode('utf-8')

# Categorize the URL as a search or gallery URL.
def categorize_url(url: str) -> str:
    if "https://zzup.com/search/" in url:
        print("Downloading search...")
        return "search"
    elif "https://zzup.com/content/" in url:
        print("Downloading gallery...")
        return "gallery"
    else:
        print("Invalid URL. Examples: \n- https://zzup.com/search/my_search/index.html\n- https://zzup.com/content/ABCDEFGHIJ==/Gallery_Name/ABC=/index.html")
        return None

def main():
    # Parse the command-line arguments
    parser = argparse.ArgumentParser(description='Download images from zzup.')
    parser.add_argument('url', type=str, nargs='?', help='The URL to download directly. Can be a search or gallery URL. Example: python3 zzup.py "https://zzup.com/search/my_search/index.html" ')
    parser.add_argument('-i', '--input', type=str, help='Input a file of URLs. Plain text file with one URL per line.')
    parser.add_argument('-o', '--output', type=str, default=".", help='The output directory to save the files. (default: current directory)')
    parser.add_argument('--threads', type=int, default=4, help='Number of threads to use (default: 4).')
    parser.add_argument('--examples', action='store_true', help='Show examples of how to use the script.')
    
    args = parser.parse_args()

    # number of threads to use moved to cli args
    NUM_PROCESSES = args.threads
    output_dir = args.output
    
    # show examples and exit
    if args.examples:
        print("Examples of how to use the script:")
        print('Download a single gallery or a search: python3 zzup.py "https://zzup.com/content/ABCDEFGHIJ==/Gallery_Name/ABC=/index.html"')
        print('Download using a file list: python3 zzup.py -i urls.txt')
        print('Download to a specific directory: python3 zzup.py "https://zzup.com/search/my_search/index.html" -o /path/to/directory')
        print('Download using 8 threads: python3 zzup.py "https://zzup.com/search/my_search/index.html" --threads 8')
        print('Download using 8 threads and save to a specific directory: python3 zzup.py "https://zzup.com/search/my_search/index.html" -o /path/to/directory --threads 8')
        print('See this message: python3 zzup.py --examples')
        return

    # determine if we are taking in a url or a file and download accordingly
    if args.url:
        url = args.url
        new_url = categorize_url(url)
        if new_url == "search":
            download_collection(url, NUM_PROCESSES, output_dir)
        elif new_url == "gallery":
            download_gallery(url, NUM_PROCESSES, output_dir)
    elif args.input:
        with open(args.input, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
            for url in urls:
                new_url = categorize_url(url)
                if new_url == "search":
                    download_collection(url, NUM_PROCESSES, output_dir)
                elif new_url == "gallery":
                    download_gallery(url, NUM_PROCESSES, output_dir)

if __name__ == "__main__":
    main()
