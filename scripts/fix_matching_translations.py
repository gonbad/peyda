#!/usr/bin/env python
"""
Script to fix Persian translations in matching questions using words.csv as source of truth.
"""
import json
import csv
import re
import unicodedata

# Arabic diacritics (tashkeel/اعراب) to remove for normalization
ARABIC_DIACRITICS = re.compile(r'[\u064B-\u0652\u0670\u0640]')  # Fatha, Damma, Kasra, Sukun, etc.
# Quranic pause/stop marks
QURAN_MARKS = re.compile(r'[\u06D6-\u06ED\u0615-\u061A]')  # ۖ ۗ ۘ ۙ ۚ ۛ ۜ etc.

def normalize_arabic(text):
    """Remove Arabic diacritics (اعراب) and Quranic marks from text for comparison."""
    if not text:
        return text
    # Remove Quranic marks first
    normalized = QURAN_MARKS.sub('', text)
    # Remove diacritics
    normalized = ARABIC_DIACRITICS.sub('', normalized)
    # Remove extra whitespace and strip
    normalized = ' '.join(normalized.split())
    return normalized

def load_translations_from_csv(csv_path):
    """Load Arabic->Persian translations from CSV file."""
    translations = {}
    normalized_translations = {}  # For fallback lookup without diacritics
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            arabic = row['Word'].strip()
            persian = row['Translation'].strip()
            translations[arabic] = persian
            
            # Also store normalized version for fallback
            normalized = normalize_arabic(arabic)
            if normalized not in normalized_translations:
                normalized_translations[normalized] = persian
    
    return translations, normalized_translations

def fix_matching_questions(json_path, translations, normalized_translations):
    """Fix Persian translations in matching questions."""
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    not_found = []
    fixed_count = 0
    total_pairs = 0
    
    for item in data:
        if item.get('model') == 'questions.question':
            fields = item.get('fields', {})
            if fields.get('question_type') == 'matching':
                content = fields.get('content', {})
                pairs = content.get('pairs', [])
                
                for pair in pairs:
                    total_pairs += 1
                    arabic = pair.get('arabic', '').strip()
                    old_persian = pair.get('persian', '')
                    
                    # Try exact match first
                    if arabic in translations:
                        new_persian = translations[arabic]
                        if new_persian != old_persian:
                            pair['persian'] = new_persian
                            fixed_count += 1
                    else:
                        # Try normalized match (without diacritics)
                        normalized = normalize_arabic(arabic)
                        if normalized in normalized_translations:
                            new_persian = normalized_translations[normalized]
                            if new_persian != old_persian:
                                pair['persian'] = new_persian
                                fixed_count += 1
                        else:
                            not_found.append({
                                'arabic': arabic,
                                'normalized': normalized,
                                'old_persian': old_persian,
                                'question_pk': item.get('pk')
                            })
    
    # Write updated JSON back
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return not_found, fixed_count, total_pairs

def main():
    csv_path = '/home/omid/projects/peyda/backend/words.csv'
    json_path = '/home/omid/projects/peyda/config/develop/data2.json'
    
    print("Loading translations from CSV...")
    translations, normalized_translations = load_translations_from_csv(csv_path)
    print(f"Loaded {len(translations)} translations")
    
    print("\nFixing matching questions...")
    not_found, fixed_count, total_pairs = fix_matching_questions(json_path, translations, normalized_translations)
    
    print(f"\n=== REPORT ===")
    print(f"Total pairs processed: {total_pairs}")
    print(f"Translations fixed: {fixed_count}")
    print(f"Words not found in CSV: {len(not_found)}")
    
    if not_found:
        print(f"\n=== WORDS NOT FOUND ({len(not_found)}) ===")
        # Group by arabic word to avoid duplicates
        unique_not_found = {}
        for item in not_found:
            key = item['arabic']
            if key not in unique_not_found:
                unique_not_found[key] = item
        
        for item in unique_not_found.values():
            print(f"Arabic: {item['arabic']}")
            print(f"  Normalized: {item['normalized']}")
            print(f"  Current Persian: {item['old_persian']}")
            print(f"  Question PK: {item['question_pk']}")
            print()

def generate_report():
    """Generate a clean report of not-found words."""
    csv_path = '/home/omid/projects/peyda/backend/words.csv'
    json_path = '/home/omid/projects/peyda/config/develop/data2.json'
    
    translations, normalized_translations = load_translations_from_csv(csv_path)
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    not_found = {}
    found_count = 0
    total_pairs = 0
    
    for item in data:
        if item.get('model') == 'questions.question':
            fields = item.get('fields', {})
            if fields.get('question_type') == 'matching':
                content = fields.get('content', {})
                pairs = content.get('pairs', [])
                
                for pair in pairs:
                    total_pairs += 1
                    arabic = pair.get('arabic', '').strip()
                    persian = pair.get('persian', '')
                    
                    # Try exact match first
                    if arabic in translations:
                        found_count += 1
                    else:
                        # Try normalized match
                        normalized = normalize_arabic(arabic)
                        if normalized in normalized_translations:
                            found_count += 1
                        else:
                            if arabic not in not_found:
                                not_found[arabic] = {
                                    'normalized': normalized,
                                    'persian': persian,
                                    'count': 0
                                }
                            not_found[arabic]['count'] += 1
    
    print(f"=== TRANSLATION COVERAGE REPORT ===")
    print(f"Total pairs: {total_pairs}")
    print(f"Found in CSV: {found_count}")
    print(f"Unique words not in CSV: {len(not_found)}")
    print(f"\n=== WORDS NOT FOUND IN CSV ({len(not_found)} unique) ===\n")
    
    # Sort by count descending
    sorted_not_found = sorted(not_found.items(), key=lambda x: -x[1]['count'])
    
    for arabic, info in sorted_not_found:
        print(f"{arabic}\t{info['persian']}\t(appears {info['count']}x)")

if __name__ == '__main__':
    main()
    print("\n" + "="*50 + "\n")
    generate_report()
