import urllib.request
import json
import ssl
import sys
import re
from pathlib import Path

# Fix potential SSL certificate issues
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch_roadmap_data(roadmap_name):
    """
    Fetches the main structure of a roadmap and all associated markdown content
    from the developer-roadmap open source repository.
    """
    base_url = "https://raw.githubusercontent.com/kamranahmedse/developer-roadmap/master/src/data/roadmaps"
    
    # Roadmap JSON usually lives at `.../roadmaps/{name}/{name}.json`
    json_url = f"{base_url}/{roadmap_name}/{roadmap_name}.json"
    
    print(f"Fetching roadmap structure for: {roadmap_name}")
    try:
        response = urllib.request.urlopen(json_url, context=ctx)
        data = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error fetching roadmap '{roadmap_name}': {e}")
        print("Tip: Are you sure you got the name right? (e.g. 'devops', 'backend', 'frontend')")
        sys.exit(1)
        
    nodes = data.get('nodes', [])
    print(f"Found {len(nodes)} total structural nodes.")
    
    # We only care about nodes that have a label (like topics)
    topics = []
    for n in nodes:
        node_type = n.get('type')
        label = n.get('data', {}).get('label')
        y_pos = n.get('position', {}).get('y', 0)
        
        if node_type in ['topic', 'subtopic'] and label:
            # The ID of the node often maps to the markdown content file
            node_id = n.get('id')
            topics.append({
                'id': node_id,
                'label': label,
                'type': node_type,
                'y': y_pos
            })
            
    # Sort chronologically (top to bottom on the visual map)
    topics.sort(key=lambda x: x['y'])
    
    # Now we need to fetch the detailed markdown content for each topic.
    # The content files are stored in `.../roadmaps/{name}/content/*.md`.
    # Unfortunately, GitHub API doesn't easily let us list files without auth, 
    # and the raw URLs include a hash. However, the exact markdown filename 
    # format is usually `{slug}@{node_id}.md` or just `{node_id}.md` in the tree.
    
    # To bypass raw listing limits, we fetch the github API tree
    api_url = f"https://api.github.com/repos/kamranahmedse/developer-roadmap/contents/src/data/roadmaps/{roadmap_name}/content"
    
    content_map = {}
    try:
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, context=ctx)
        tree = json.loads(res.read().decode('utf-8'))
        
        print(f"Found {len(tree)} content files associated with this roadmap.")
        # Map IDs to raw download URLs
        for item in tree:
            if item['name'].endswith('.md'):
                # Extract the ID from the filename (usually comes after an @ or is the whole name)
                # Example: python@1234.md
                match = re.search(r'@([^.]+)\.md$', item['name'])
                if match:
                    content_map[match.group(1)] = item['download_url']
                elif '-' in item['name'] and not '@' in item['name']: # fallback for older formats
                    content_map[item['name'].split('.')[0]] = item['download_url']

    except Exception as e:
        print(f"Could not fetch detailed markdown content directory: {e}")
        print("Continuing with just structural data...")
        
    # Build the final markdown document
    out_dir = Path("references")
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"{roadmap_name}_roadmap.md"
    
    print(f"\nCompiling {roadmap_name} roadmap into {out_file}...")
    
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(f"# The {roadmap_name.capitalize()} Roadmap\n\n")
        f.write("> Automatically extracted from roadmap.sh public repository.\n\n")
        
        for topic in topics:
            heading = "##" if topic['type'] == 'topic' else "###"
            f.write(f"{heading} {topic['label']}\n\n")
            
            # Fetch the detailed explanation if it exists
            content_url = content_map.get(topic['id'])
            if content_url:
                try:
                    content_res = urllib.request.urlopen(content_url, context=ctx)
                    markdown_body = content_res.read().decode('utf-8')
                    
                    # Clean up the frontmatter from their markdown (between ---)
                    markdown_body = re.sub(r'^---[\s\S]*?---\n', '', markdown_body)
                    f.write(f"{markdown_body.strip()}\n\n")
                except Exception as e:
                    f.write(f"*(Failed to fetch detailed description)*\n\n")
            else:
                 f.write(f"*(No detailed description provided)*\n\n")
                 
            f.write("---\n\n")
            
    print(f"Success! Saved full structured roadmap to: {out_file.absolute()}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_roadmap.py [roadmap_name]")
        print("Example: python fetch_roadmap.py devops")
        sys.exit(1)
        
    roadmap = sys.argv[1].lower().strip()
    fetch_roadmap_data(roadmap)
