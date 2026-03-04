import requests
from bs4 import BeautifulSoup
from pprint import pprint

url = "https://nios.ac.in/online-course-material/sr-secondary-courses.aspx"
headers = {"User-Agent": "Mozilla/5.0"}

response = requests.get(url, headers=headers)
soup = BeautifulSoup(response.content, 'html.parser')

links = soup.find_all('a', href=True)
print(f"Total links: {len(links)}")

subjects = []
for a in links:
    if "material" in a['href'].lower() and len(a.text.strip()) > 3:
        subjects.append({"href": a['href'], "text": a.text.strip()})

pprint(subjects[:20])
