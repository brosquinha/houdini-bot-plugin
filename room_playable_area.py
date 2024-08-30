import csv
import itertools
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from argparse import ArgumentParser

TMP_PATH = '/tmp'
OUTPUT_SVG = 'playable_area.svg'
OUTPUT_CSV = 'playable_area.csv'

def extract_xml_from_swf(filename: str) -> str:
    output_path = os.path.join(TMP_PATH, "output.xml")
    with open(output_path, 'a'):
        pass
    
    _run_command(["docker", "run", "-u", "1000:1000", "--rm", "-it",
                  "-v", f"{os.path.abspath(filename)}:/file.swf",
                  "-v", f"{output_path}:/output.xml", "jpexs", "-swf2xml", "/file.swf", "/output.xml"])
    
    return output_path

def get_shape_from_xml(filename: str) -> str:
    root = ET.parse(filename)
    block_mc_element = root.find('.//item[@name="block_mc"]')
    ch_id = block_mc_element.attrib.get('characterId')
    target_element = root.find(f'.//item[@spriteId="{ch_id}"]//item[@type="PlaceObject2Tag"]')

    return target_element.attrib.get('characterId')

def extract_svg_from_swf(filename: str, svg_name: str) -> str:
    output_path = os.path.join(TMP_PATH, "outputs")
    os.makedirs(output_path, exist_ok=True)
    
    _run_command(["docker", "run", "-u", "1000:1000", "--rm", "-it",
                  "-v", f"{os.path.abspath(filename)}:/file.swf",
                  "-v", f"{output_path}:/outputs", "jpexs", "-export", "shape", "/outputs", "/file.swf"])
    
    shutil.copy(os.path.join(output_path, f"{svg_name}.svg"), f"./{OUTPUT_SVG}")
    return OUTPUT_SVG
    
def get_svg_path(filename: str) -> str:
    root = ET.parse(filename)
    path = root.find('.//{http://www.w3.org/2000/svg}path')
    return path.attrib.get('d')

def get_point_list_from_svg_path(svg_path: str) -> list[float]:
    matches = []
    for match in re.finditer(
        r'M\s?([\d\.]+ [\d\.]+)|Q\s?[\d\.]+ [\d\.]+ ([\d\.]+ [\d\.]+)((?: [\d\.]+ [\d\.]+ [\d\.]+ [\d\.]+)*)|L\s?([\d\.]+ [\d\.]+)((?: [\d\.]+ [\d\.]+)*)',
        svg_path
    ):
        for group in [1, 2, 4]:
            if content := match.group(group):
                matches.append(tuple(content.split(' ')))
                
        if content := match.group(5):
            matches.extend(_batched(content.strip().split(' ')))
            
        if content := match.group(3):
            matches.extend([x for _, x in _batched(list(_batched(content.strip().split(' '))))])
    return [(float(a), float(b)) for a, b in matches]

def export_point_list_to_csv(points: list[float]):
    with open(OUTPUT_CSV, 'w+') as f:
        writer = csv.writer(f)
        for x, y in points:
            writer.writerow([x, y])

def _run_command(cmd_args: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd_args, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(e.output.decode())
        print(e.stderr.decode())
        raise e
    
def _batched(iterable, n=2):
    iterator = iter(iterable)
    while batch := tuple(itertools.islice(iterator, n)):
        yield batch
    
def main(filename: str, iteractive: bool=False):
    svg_name = get_shape_from_xml(extract_xml_from_swf(filename))
    
    svg_path = get_svg_path(extract_svg_from_swf(filename, svg_name))
    export_point_list_to_csv(get_point_list_from_svg_path(svg_path))
    print(svg_path)
    
    if iteractive:
        edited_path = input("Enter edited SVG path: ")
        print(get_point_list_from_svg_path(edited_path))
    
if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument("room_file_path")
    parser.add_argument("--iteractive", "-i", action='store_true', help="Enter edited SVG path using a tool like https://yqnn.github.io/svg-path-editor/")
    args = parser.parse_args()
    
    main(args.room_file_path, iteractive=args.iteractive)
