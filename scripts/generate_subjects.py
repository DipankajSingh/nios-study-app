import json
from scrape_nios import scrape_subjects

def main():
    print("Fetching Class 10 subjects...")
    url_10 = "https://nios.ac.in/online-course-material/secondary-courses.aspx"
    subjects_10 = scrape_subjects(url_10, is_class_12=False)
    
    with open('subjects_10.json', 'w') as f:
        json.dump(subjects_10, f, indent=4)
    print(f"Saved {len(subjects_10)} Class 10 subjects to subjects_10.json\n")
        
    print("Fetching Class 12 subjects...")
    url_12 = "https://nios.ac.in/online-course-material/sr-secondary-courses.aspx"
    subjects_12 = scrape_subjects(url_12, is_class_12=True)
    
    with open('subjects_12.json', 'w') as f:
        json.dump(subjects_12, f, indent=4)
    print(f"Saved {len(subjects_12)} Class 12 subjects to subjects_12.json")

if __name__ == '__main__':
    main()
