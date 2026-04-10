import requests
from bs4 import BeautifulSoup

URL = "https://cses.fi/user/416103"

def get_solved():
    html = requests.get(URL).text
    soup = BeautifulSoup(html, "html.parser")
    
    # "Task statistics: X completed, Y tried"
    stats = soup.find("td", string="Task statistics:")
    solved = stats.find_next("td").text.split()[0]
    
    return int(solved)

def generate_svg(solved):
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="220" height="40">
      <rect width="220" height="40" fill="#0a84ff"/>
      <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="white" font-size="18">
        CSES: {solved} solved
      </text>
    </svg>
    """
    with open("generated/cses_solved.svg", "w", encoding="utf-8") as f:
        f.write(svg)

if __name__ == "__main__":
    solved = get_solved()
    generate_svg(solved)
    print("Updated:", solved)
