import difflib
import json
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFilter
import numpy as np
import html5lib
from html5lib import html5parser
from html5lib import serializer
from html5lib.treebuilders import getTreeBuilder
import aiofiles
import asyncio

class DiffResult:
    def __init__(self, before_path: str, after_path: str):
        self.before_path = before_path
        self.after_path = after_path
        self.changes = []
        self.metrics = {}
        self.highlights = {}
    
    def add_change(self, change_type: str, location: Any, details: Dict[str, Any]):
        self.changes.append({
            'type': change_type,
            'location': location,
            'details': details,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'before': self.before_path,
            'after': self.after_path,
            'change_count': len(self.changes),
            'changes': self.changes,
            'metrics': self.metrics,
            'highlights': list(self.highlights.keys())
        }

class DiffEngine:
    def __init__(self, output_path: str = "/app/artifacts/diffs"):
        self.output_path = Path(output_path)
        self.output_path.mkdir(parents=True, exist_ok=True)
    
    async def compare(self, before_evidence: Dict[str, Any], 
                     after_evidence: Dict[str, Any], 
                     diff_types: Optional[list] = None) -> Dict[str, DiffResult]:
        """
        Compare before and after evidence.
        Returns dict of DiffResult objects by evidence type.
        """
        if diff_types is None:
            diff_types = ['text', 'dom', 'visual']
        
        results = {}
        
        # Text-based diff (for console, storage, cookies)
        if 'text' in diff_types:
            text_results = await self._compare_text_artifacts(before_evidence, after_evidence)
            results.update(text_results)
        
        # DOM diff
        if 'dom' in diff_types and 'dom' in before_evidence and 'dom' in after_evidence:
            dom_result = await self._compare_dom(
                before_evidence['dom']['path'],
                after_evidence['dom']['path']
            )
            results['dom'] = dom_result
        
        # Visual diff (for screenshots)
        if 'visual' in diff_types:
            visual_results = await self._compare_visual_artifacts(before_evidence, after_evidence)
            results.update(visual_results)
        
        return results
    
    async def _compare_text_artifacts(self, before: Dict[str, Any], 
                                    after: Dict[str, Any]) -> Dict[str, DiffResult]:
        """Compare text-based artifacts (JSON, HTML)."""
        results = {}
        
        for artifact_type in ['console', 'cookies', 'storage']:
            if artifact_type in before and artifact_type in after:
                before_path = before[artifact_type]['path']
                after_path = after[artifact_type]['path']
                
                result = DiffResult(before_path, after_path)
                
                try:
                    async with aiofiles.open(before_path, 'r', encoding='utf-8') as f:
                        before_text = await f.read()
                    
                    async with aiofiles.open(after_path, 'r', encoding='utf-8') as f:
                        after_text = await f.read()
                    
                    # Parse as JSON if possible
                    try:
                        before_data = json.loads(before_text)
                        after_data = json.loads(after_text)
                        
                        # JSON comparison
                        diff = self._json_diff(before_data, after_data)
                        for change in diff:
                            result.add_change(change['type'], change.get('path'), change)
                        
                        result.metrics['json_changes'] = len(diff)
                        
                    except json.JSONDecodeError:
                        # Text diff
                        diff = self._text_diff(before_text, after_text)
                        for change in diff:
                            result.add_change('text', change['line'], change)
                        
                        result.metrics['text_changes'] = len(diff)
                    
                    results[artifact_type] = result
                    
                except Exception as e:
                    result.add_change('error', None, {'error': str(e)})
                    results[artifact_type] = result
        
        return results
    
    def _json_diff(self, before: Any, after: Any, path: str = '') -> List[Dict[str, Any]]:
        """Recursive JSON diff."""
        changes = []
        
        if isinstance(before, dict) and isinstance(after, dict):
            # Compare keys
            all_keys = set(before.keys()) | set(after.keys())
            
            for key in all_keys:
                new_path = f"{path}.{key}" if path else key
                
                if key in before and key in after:
                    # Both have key, compare values
                    changes.extend(self._json_diff(before[key], after[key], new_path))
                elif key in before:
                    # Key removed
                    changes.append({
                        'type': 'removed',
                        'path': new_path,
                        'before': before[key],
                        'after': None
                    })
                else:
                    # Key added
                    changes.append({
                        'type': 'added',
                        'path': new_path,
                        'before': None,
                        'after': after[key]
                    })
        
        elif isinstance(before, list) and isinstance(after, list):
            # Compare lists
            max_len = max(len(before), len(after))
            
            for i in range(max_len):
                new_path = f"{path}[{i}]"
                
                if i < len(before) and i < len(after):
                    changes.extend(self._json_diff(before[i], after[i], new_path))
                elif i < len(before):
                    changes.append({
                        'type': 'removed',
                        'path': new_path,
                        'before': before[i],
                        'after': None
                    })
                else:
                    changes.append({
                        'type': 'added',
                        'path': new_path,
                        'before': None,
                        'after': after[i]
                    })
        
        else:
            # Compare primitive values
            if before != after:
                changes.append({
                    'type': 'modified',
                    'path': path,
                    'before': before,
                    'after': after
                })
        
        return changes
    
    def _text_diff(self, before: str, after: str) -> List[Dict[str, Any]]:
        """Generate text diff using difflib."""
        changes = []
        
        before_lines = before.splitlines()
        after_lines = after.splitlines()
        
        diff = difflib.unified_diff(
            before_lines,
            after_lines,
            lineterm='',
            n=3
        )
        
        diff_list = list(diff)
        
        if len(diff_list) > 0:
            changes.append({
                'type': 'text_diff',
                'diff': '\n'.join(diff_list),
                'line_count': len(diff_list)
            })
        
        return changes
    
    async def _compare_dom(self, before_path: str, after_path: str) -> DiffResult:
        """Compare DOM structure."""
        result = DiffResult(before_path, after_path)
        
        try:
            async with aiofiles.open(before_path, 'r', encoding='utf-8') as f:
                before_html = await f.read()
            
            async with aiofiles.open(after_path, 'r', encoding='utf-8') as f:
                after_html = await f.read()
            
            # Parse HTML
            parser = html5parser.HTMLParser(tree=getTreeBuilder("dom"))
            before_doc = parser.parse(before_html)
            after_doc = parser.parse(after_html)
            
            # Compare structure
            changes = self._dom_diff(before_doc, after_doc)
            
            for change in changes:
                result.add_change(change['type'], change.get('xpath'), change)
            
            result.metrics['dom_changes'] = len(changes)
            
            # Generate HTML diff
            html_diff = self._generate_html_diff(before_html, after_html)
            diff_path = Path(before_path).parent / "dom_diff.html"
            
            async with aiofiles.open(diff_path, 'w', encoding='utf-8') as f:
                await f.write(html_diff)
            
            result.highlights['dom_diff'] = str(diff_path)
            
        except Exception as e:
            result.add_change('error', None, {'error': str(e)})
        
        return result
    
    def _dom_diff(self, before_node, after_node, xpath: str = '/') -> List[Dict[str, Any]]:
        """Recursive DOM diff."""
        changes = []
        
        # Compare node types
        if before_node.nodeType != after_node.nodeType:
            changes.append({
                'type': 'node_type_changed',
                'xpath': xpath,
                'before': before_node.nodeType,
                'after': after_node.nodeType
            })
            return changes
        
        # Compare element nodes
        if before_node.nodeType == before_node.ELEMENT_NODE:
            # Compare tag names
            if before_node.tagName != after_node.tagName:
                changes.append({
                    'type': 'tag_changed',
                    'xpath': xpath,
                    'before': before_node.tagName,
                    'after': after_node.tagName
                })
            
            # Compare attributes
            before_attrs = dict(before_node.attributes.items()) if before_node.attributes else {}
            after_attrs = dict(after_node.attributes.items()) if after_node.attributes else {}
            
            all_attrs = set(before_attrs.keys()) | set(after_attrs.keys())
            
            for attr in all_attrs:
                attr_xpath = f"{xpath}/@{attr}"
                
                if attr in before_attrs and attr in after_attrs:
                    if before_attrs[attr] != after_attrs[attr]:
                        changes.append({
                            'type': 'attribute_changed',
                            'xpath': attr_xpath,
                            'before': before_attrs[attr],
                            'after': after_attrs[attr]
                        })
                elif attr in before_attrs:
                    changes.append({
                        'type': 'attribute_removed',
                        'xpath': attr_xpath,
                        'before': before_attrs[attr],
                        'after': None
                    })
                else:
                    changes.append({
                        'type': 'attribute_added',
                        'xpath': attr_xpath,
                        'before': None,
                        'after': after_attrs[attr]
                    })
            
            # Compare child nodes
            before_children = list(before_node.childNodes)
            after_children = list(after_node.childNodes)
            
            # Compare text content for text nodes
            text_nodes_before = [c for c in before_children if c.nodeType == c.TEXT_NODE]
            text_nodes_after = [c for c in after_children if c.nodeType == c.TEXT_NODE]
            
            if text_nodes_before or text_nodes_after:
                before_text = ''.join(c.data for c in text_nodes_before).strip()
                after_text = ''.join(c.data for c in text_nodes_after).strip()
                
                if before_text != after_text:
                    changes.append({
                        'type': 'text_changed',
                        'xpath': f"{xpath}/text()",
                        'before': before_text,
                        'after': after_text
                    })
            
            # Compare element children
            elem_children_before = [c for c in before_children if c.nodeType == c.ELEMENT_NODE]
            elem_children_after = [c for c in after_children if c.nodeType == c.ELEMENT_NODE]
            
            # Compare by position for now (simplified)
            for i in range(max(len(elem_children_before), len(elem_children_after))):
                child_xpath = f"{xpath}/*[{i+1}]"
                
                if i < len(elem_children_before) and i < len(elem_children_after):
                    changes.extend(self._dom_diff(
                        elem_children_before[i],
                        elem_children_after[i],
                        child_xpath
                    ))
                elif i < len(elem_children_before):
                    changes.append({
                        'type': 'element_removed',
                        'xpath': child_xpath,
                        'before': elem_children_before[i].tagName,
                        'after': None
                    })
                else:
                    changes.append({
                        'type': 'element_added',
                        'xpath': child_xpath,
                        'before': None,
                        'after': elem_children_after[i].tagName
                    })
        
        return changes
    
    def _generate_html_diff(self, before_html: str, after_html: str) -> str:
        """Generate side-by-side HTML diff."""
        before_lines = before_html.splitlines()
        after_lines = after_html.splitlines()
        
        diff = difflib.HtmlDiff(wrapcolumn=80)
        html_diff = diff.make_file(
            before_lines,
            after_lines,
            "Before",
            "After",
            context=True,
            numlines=3
        )
        
        # Add styling
        styled_html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>DOM Diff</title>
            <style>
                body {{ font-family: monospace; margin: 20px; }}
                table.diff {{ width: 100%; border-collapse: collapse; }}
                .diff_header {{ background-color: #e0e0e0; }}
                td.diff_header {{ text-align: right; }}
                .diff_next {{ background-color: #c0c0c0; }}
                .diff_add {{ background-color: #aaffaa; }}
                .diff_chg {{ background-color: #ffff77; }}
                .diff_sub {{ background-color: #ffaaaa; }}
                .highlight {{ background-color: yellow; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>DOM Comparison</h1>
            <p>Generated: {datetime.utcnow().isoformat()}</p>
            {html_diff}
        </body>
        </html>
        '''
        
        return styled_html
    
    async def _compare_visual_artifacts(self, before: Dict[str, Any], 
                                      after: Dict[str, Any]) -> Dict[str, DiffResult]:
        """Compare visual artifacts (screenshots)."""
        results = {}
        
        for artifact_type in ['fullpage', 'viewport']:
            if artifact_type in before and artifact_type in after:
                before_path = before[artifact_type]['path']
                after_path = after[artifact_type]['path']
                
                result = DiffResult(before_path, after_path)
                
                try:
                    # Load images
                    before_img = Image.open(before_path)
                    after_img = Image.open(after_path)
                    
                    # Ensure same size
                    if before_img.size != after_img.size:
                        # Resize to match
                        max_width = max(before_img.width, after_img.width)
                        max_height = max(before_img.height, after_img.height)
                        
                        before_img = before_img.resize((max_width, max_height), Image.Resampling.LANCZOS)
                        after_img = after_img.resize((max_width, max_height), Image.Resampling.LANCZOS)
                    
                    # Calculate difference
                    diff_img = ImageChops.difference(before_img, after_img)
                    
                    # Convert to grayscale for analysis
                    diff_gray = diff_img.convert('L')
                    
                    # Calculate metrics
                    diff_array = np.array(diff_gray)
                    non_zero = np.count_nonzero(diff_array)
                    total_pixels = diff_array.size
                    diff_percentage = (non_zero / total_pixels) * 100
                    
                    result.metrics.update({
                        'total_pixels': total_pixels,
                        'changed_pixels': non_zero,
                        'change_percentage': diff_percentage,
                        'image_width': before_img.width,
                        'image_height': before_img.height
                    })
                    
                    # Generate diff image with highlights
                    if non_zero > 0:
                        # Create highlighted diff
                        highlight_img = self._create_highlight_diff(before_img, after_img, diff_array)
                        
                        # Save diff images
                        diff_output = Path(before_path).parent
                        diff_path = diff_output / f"{artifact_type}_diff.png"
                        highlight_path = diff_output / f"{artifact_type}_highlight.png"
                        
                        diff_img.save(diff_path)
                        highlight_img.save(highlight_path)
                        
                        result.highlights['diff'] = str(diff_path)
                        result.highlights['highlight'] = str(highlight_path)
                        
                        # Add change regions
                        regions = self._detect_change_regions(diff_array)
                        for i, region in enumerate(regions):
                            result.add_change('visual', region['bbox'], {
                                'region_id': i,
                                'pixel_count': region['pixel_count'],
                                'bbox': region['bbox']
                            })
                    
                    results[artifact_type] = result
                    
                except Exception as e:
                    result.add_change('error', None, {'error': str(e)})
                    results[artifact_type] = result
        
        return results
    
    def _create_highlight_diff(self, before_img: Image.Image, after_img: Image.Image, 
                             diff_array: np.ndarray) -> Image.Image:
        """Create highlighted diff image."""
        # Create composite
        composite = Image.new('RGB', before_img.size, (255, 255, 255))
        
        # Convert to RGB if needed
        before_rgb = before_img.convert('RGB')
        after_rgb = after_img.convert('RGB')
        
        # Create mask
        threshold = 30
        mask = diff_array > threshold
        
        # Convert mask to image
        mask_img = Image.fromarray((mask * 255).astype('uint8'))
        
        # Apply blur to mask for smoother highlights
        mask_blur = mask_img.filter(ImageFilter.GaussianBlur(radius=2))
        
        # Create highlight layer
        highlight = Image.new('RGB', before_img.size, (255, 255, 0))  # Yellow
        highlight.putalpha(mask_blur)
        
        # Composite images
        composite.paste(before_rgb, (0, 0))
        composite.paste(after_rgb, (before_img.width // 2, 0))
        composite.alpha_composite(highlight)
        
        # Add separator line
        draw = ImageDraw.Draw(composite)
        mid_x = before_img.width // 2
        draw.line([(mid_x, 0), (mid_x, before_img.height)], 
                 fill=(0, 0, 0), width=2)
        
        # Add labels
        draw.text((10, 10), "Before", fill=(0, 0, 0))
        draw.text((mid_x + 10, 10), "After", fill=(0, 0, 0))
        
        return composite
    
    def _detect_change_regions(self, diff_array: np.ndarray, 
                             min_region_size: int = 100) -> List[Dict[str, Any]]:
        """Detect contiguous regions of change."""
        from scipy import ndimage
        
        regions = []
        
        # Threshold the diff
        threshold = 30
        binary = diff_array > threshold
        
        # Label connected components
        labeled, num_features = ndimage.label(binary)
        
        for i in range(1, num_features + 1):
            # Get coordinates of this region
            coords = np.argwhere(labeled == i)
            
            if len(coords) >= min_region_size:
                # Calculate bounding box
                y_min, x_min = coords.min(axis=0)
                y_max, x_max = coords.max(axis=0)
                
                regions.append({
                    'bbox': (int(x_min), int(y_min), int(x_max), int(y_max)),
                    'pixel_count': len(coords),
                    'center': (int((x_min + x_max) / 2), int((y_min + y_max) / 2))
                })
        
        return regions
