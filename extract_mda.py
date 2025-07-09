import pandas as pd
from collections import Counter
import re

# This script is designed to extract the "Management Discussion & Analysis" (MD&A)
# section from the annual reports of Chinese A-share listed companies.
# It employs several strategies to locate and isolate this specific section
# from the full text of a report.

def _get_toc_range(text: str) -> tuple[int, int]:
    """
    Identifies the approximate start and end positions of the Table of Contents (TOC).
    It searches for the Chinese characters for "Table of Contents" ("目录").

    Args:
        text: The full text of the annual report.

    Returns:
        A tuple containing the start and end index for the presumed TOC section.
    """
    try:
        # Find the starting position of "目录" (Table of Contents).
        toc_start_index = [match.start() for match in re.finditer(r'\n目\s*录', text)][0]
        # Assume the TOC is within the next 2000 characters. This is an approximation.
        toc_end_index = toc_start_index + 2000
    except IndexError:
        # If "目录" is not found, assume the TOC is at the beginning of the document.
        toc_start_index = 0
        toc_end_index = 2500
    return toc_start_index, toc_end_index

def _get_mda_keywords_pattern(keywords_pattern: str) -> str:
    """
    Returns a regex pattern for MD&A keywords.
    If no custom pattern is provided, it uses a default list of common Chinese
    phrases for "Management Discussion & Analysis".

    Args:
        keywords_pattern: A user-supplied regex pattern for MD&A keywords.

    Returns:
        A regex pattern string.
    """
    if not keywords_pattern:
        # This default pattern includes many common synonyms for MD&A in Chinese reports.
        # e.g., "董事会报告" (Board of Directors' Report), "管理层讨论与分析" (Management Discussion & Analysis), etc.
        return (
            '董事会报告|董事会报告与管理讨论|企业运营与管理评述|经营总结与分析|'
            '管理层评估与未来展望|董事局报告|管理层讨论与分析|经营情况讨论与分析|'
            '经营业绩分析|业务回顾与展望|公司经营分析|管理层评论与分析|'
            '执行摘要与业务回顾|业务运营分析'
        )
    return keywords_pattern

def _get_chinese_number_maps() -> tuple[dict, dict]:
    """
    Provides dictionaries for mapping between Chinese number characters and integers.

    Returns:
        A tuple containing two dictionaries:
        - char_to_int_map: Maps Chinese number characters ('一', '二', ...) to integers.
        - int_to_char_map: Maps integers to Chinese number characters.
    """
    char_to_int_map = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
    int_to_char_map = {1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六', 7: '七', 8: '八', 9: '九', 10: '十', 11: '十一', 12: '十二'}
    return char_to_int_map, int_to_char_map

def extract_mda(text: str, keywords_pattern: str = '') -> str:
    """
    Extracts the MD&A section from the text of a Chinese A-share annual report.
    It tries a primary extraction method (_extract_mda_via_toc) and falls back to a
    secondary method (_extract_mda_via_keyword_search) if the first one fails.

    Args:
        text: The full text of the annual report.
        keywords_pattern: An optional regex pattern to locate the MD&A section.
                          If empty, a default pattern of common MD&A titles is used.

    Returns:
        The extracted MD&A content as a string, or an empty string if not found.
    """
    try:
        # Primary strategy: Use the Table of Contents to find the section.
        mda_content = _extract_mda_via_toc(text, keywords_pattern=keywords_pattern)
    except Exception:
        try:
            # Fallback strategy: Search directly for section headers with keywords.
            mda_content = _extract_mda_via_keyword_search(text, keywords_pattern=keywords_pattern)
        except Exception:
            # If both methods fail, return an empty string.
            mda_content = ''
    return mda_content

def _extract_mda_via_toc(text: str, keywords_pattern: str = '') -> str:
    """
    Primary MD&A extraction strategy.
    It parses the Table of Contents (TOC) to identify the MD&A section and the
    section immediately following it, then uses their titles as delimiters to
    extract the content from the main body of the report.

    Args:
        text: The full text of the annual report.
        keywords_pattern: A regex pattern for MD&A keywords.

    Returns:
        The extracted MD&A content as a string.
    """
    toc_start_index, toc_end_index = _get_toc_range(text)
    mda_keywords_pattern = _get_mda_keywords_pattern(keywords_pattern)

    # Extract the text of the TOC.
    toc_text = text[toc_start_index:toc_end_index]
    
    # Split the TOC by section markers like "第一节" (Section 1), "第二章" (Chapter 2).
    # This creates a list of section titles.
    toc_section_titles = re.split(r'\n第[一二三四五六七八九十][节|章]', toc_text)[1:]
    toc_section_titles = [re.sub(r'\d+|\.', '', title).strip() for title in toc_section_titles]
    
    # Find all section markers (e.g., "第一节").
    toc_section_markers = re.findall(r'\n第[一二三四五六七八九十][节|章]', toc_text)

    if toc_section_titles and toc_section_markers:
        # Create a DataFrame to easily search the TOC titles.
        toc_df = pd.DataFrame({'title': toc_section_titles})
        
        # Find the index of the MD&A section in the TOC.
        # It searches the 'title' column for our keywords pattern.
        mda_toc_index = toc_df[toc_df.title.fillna('').str.contains(mda_keywords_pattern)].index[0]

        # Reconstruct the full title of the MD&A section and the next section.
        mda_section_title = toc_section_markers[mda_toc_index].replace('\n', '') + toc_section_titles[mda_toc_index]
        # Clean the title to use as a search pattern (mask) in the full text.
        mda_title_mask = re.sub(r'\d+|\. ⋯', '', mda_section_title).rstrip()

        next_section_title = toc_section_markers[mda_toc_index + 1].replace('\n', '') + toc_section_titles[mda_toc_index + 1]
        next_title_mask = re.sub(r'\d+|\. ⋯', '', next_section_title).rstrip()

        try:
            # This block handles titles that might contain spaces, e.g., "第四节 经营情况讨论与分析".
            # It splits the title and searches for both parts in close proximity to find the exact start.
            title_part1, title_part2 = re.split(r'\s', mda_title_mask)
            potential_starts = [match.start() for match in re.finditer(title_part2, text[toc_end_index:])]
            for start_pos in potential_starts:
                # Check if the first part of the title is nearby, confirming the match.
                if re.findall(title_part1, text[toc_end_index:][start_pos - 50: start_pos + 50]):
                    mda_start_index = start_pos
                    break

            next_title_part1, next_title_part2 = re.split(r'\s', next_title_mask)
            potential_ends = [match.start() for match in re.finditer(next_title_part2, text[toc_end_index:])]
            for end_pos in potential_ends:
                # Confirm the match for the next section's title.
                if re.findall(next_title_part1, text[toc_end_index:][end_pos - 50: end_pos + 50]):
                    # Ensure the end position is after the start position.
                    if end_pos > mda_start_index:
                        mda_end_index = end_pos
                        break
            
            # Return the slice of text between the start and end indexes.
            return text[toc_end_index:][mda_start_index:mda_end_index]

        except Exception:
            # A simpler fallback: split the text by the start and end titles.
            # This is less precise but works for many cases.
            raw_mda_text = mda_title_mask + text[toc_end_index:].split(mda_title_mask)[-1]
            return raw_mda_text.split(next_title_mask)[0]
            
    # If TOC parsing fails, fall back to a keyword-based search similar to the secondary function.
    else:
        char_to_int_map, int_to_char_map = _get_chinese_number_maps()
        
        # Find all Chinese numbers near instances of the MD&A keywords.
        numbers_found = []
        for match in re.finditer(mda_keywords_pattern, text):
            # Search a small window around the keyword for a number character.
            number_match = re.findall('[一二三四五六七八九十]+', text[match.start() - 10:match.start() + 10])
            if number_match:
                numbers_found.extend(number_match)

        if numbers_found:
            # The most frequent number found is likely the MD&A section number.
            most_common_section_num_char = Counter(numbers_found).most_common(1)[0][0]
            
            # Construct a precise regex pattern for the section header.
            # e.g., "\n第三节[,. ]{1,5}管理层讨论与分析"
            mda_header_pattern = r'\n[第]*[一二三四五六七八九十]{1,}[节|章]*[,，:：、. \t]{1,5}' + mda_keywords_pattern
            mda_header_full_match = [r.replace('\n', '') for r in re.findall(mda_header_pattern, text)][-1]
            
            # Determine the separator used (e.g., '、', ' ', '.').
            header_separator = re.sub(r'[\u4e00-\u9fa5]+', '', mda_header_full_match)
            
            # Construct the header for the *next* section to serve as the end delimiter.
            next_section_number = char_to_int_map[most_common_section_num_char] + 1
            next_section_header = '\n' + int_to_char_map[next_section_number] + header_separator
            
            mda_content = text.split(mda_header_full_match)[-1].split(next_section_header)[0]
            return mda_content
    
    return '' # Return empty if no method works

def _extract_mda_via_keyword_search(text: str, keywords_pattern: str = '') -> str:
    """
    Secondary MD&A extraction strategy.
    This method directly searches the text for section headers (e.g., "第三节") that
    contain MD&A keywords. It determines the section number and uses the next
    section's header as the end delimiter.

    Args:
        text: The full text of the annual report.
        keywords_pattern: A regex pattern for MD&A keywords.

    Returns:
        The extracted MD&A content as a string.
    """
    mda_keywords_pattern = _get_mda_keywords_pattern(keywords_pattern)
    char_to_int_map, int_to_char_map = _get_chinese_number_maps()

    # Find all Chinese numbers that appear near the MD&A keywords.
    numbers_found = []
    for match in re.finditer(mda_keywords_pattern, text):
        number_match = re.findall('[一二三四五六七八九十]+', text[match.start() - 10:match.start() + 10])
        if number_match:
            numbers_found.extend(number_match)

    if numbers_found:
        # Assume the most common number found is the correct section number.
        most_common_section_num_char = Counter(numbers_found).most_common(1)[0][0]
        
        # Build a regex to find the full header line of the MD&A section.
        # Pattern looks for: newline, optional "第", number, optional "节" or "章", separator, keyword.
        mda_header_pattern = r'\n[第]*[一二三四五六七八九十]{1,}[节|章]*[,，:：、. \t]{1,5}' + mda_keywords_pattern
        # Find the last matching header in the text.
        mda_header_full_match = [r.replace('\n', '') for r in re.findall(mda_header_pattern, text)][-1]

        # Isolate the punctuation/separator from the header.
        header_separator = re.sub(r'[\u4e00-\u9fa5]+', '', mda_header_full_match)

        # Construct the pattern for the next section's header to use as an end delimiter.
        # e.g., if MD&A is "第三、", next section header will likely be "第四、".
        next_section_number = char_to_int_map[most_common_section_num_char] + 1
        next_section_header_pattern = '\n' + int_to_char_map[next_section_number] + header_separator

        # Split the text by the MD&A header and then by the next section's header.
        mda_content = mda_header_full_match + text.split(mda_header_full_match)[-1].split(next_section_header_pattern)[0]
        return mda_content
        
    return '' # Return empty if no keywords and numbers are found