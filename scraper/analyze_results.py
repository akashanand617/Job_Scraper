#!/usr/bin/env python3
"""
Analyze LinkedIn job scraping results
"""

import json
from collections import Counter, defaultdict
from datetime import datetime
import re

def load_data():
    """Load all data files"""
    with open('linkedin_jobs.json', 'r') as f:
        jobs = json.load(f)
    
    with open('shard_results.json', 'r') as f:
        shard_results = json.load(f)
    
    with open('shard_mappings.json', 'r') as f:
        shard_mappings = json.load(f)
    
    return jobs, shard_results, shard_mappings

def analyze_jobs(jobs):
    """Analyze job data"""
    print("📊 JOB DATA ANALYSIS")
    print("=" * 50)
    
    # Basic stats
    total_jobs = len(jobs)
    api_jobs = len([j for j in jobs if j['source'] == 'api'])
    dom_jobs = len([j for j in jobs if j['source'] == 'dom'])
    jobs_with_dates = len([j for j in jobs if j['posted_dt']])
    reposts = len([j for j in jobs if j['is_repost']])
    
    print(f"Total jobs: {total_jobs}")
    print(f"API jobs: {api_jobs} ({api_jobs/total_jobs*100:.1f}%)")
    print(f"DOM jobs: {dom_jobs} ({dom_jobs/total_jobs*100:.1f}%)")
    print(f"Jobs with dates: {jobs_with_dates} ({jobs_with_dates/total_jobs*100:.1f}%)")
    print(f"Reposts: {reposts} ({reposts/total_jobs*100:.1f}%)")
    
    # Company analysis
    companies = [j['company_name'] for j in jobs if j['company_name'] != 'N/A']
    company_counts = Counter(companies)
    
    print(f"\n🏢 COMPANY ANALYSIS")
    print(f"Unique companies: {len(company_counts)}")
    print(f"Top 10 companies:")
    for company, count in company_counts.most_common(10):
        print(f"  {company}: {count} jobs")
    
    # URL analysis
    linkedin_urls = len([j for j in jobs if 'linkedin.com/jobs/view' in j['url']])
    external_urls = total_jobs - linkedin_urls
    
    print(f"\n🔗 URL ANALYSIS")
    print(f"LinkedIn URLs: {linkedin_urls} ({linkedin_urls/total_jobs*100:.1f}%)")
    print(f"External URLs: {external_urls} ({external_urls/total_jobs*100:.1f}%)")
    
    # Date analysis
    if jobs_with_dates > 0:
        dates = []
        for j in jobs:
            if j['posted_dt']:
                try:
                    dt_str = j['posted_dt'].replace('Z', '+00:00')
                    dt = datetime.fromisoformat(dt_str)
                    # Ensure timezone awareness
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    dates.append(dt)
                except:
                    continue
        
        if dates:
            oldest = min(dates)
            newest = max(dates)
            print(f"\n📅 DATE ANALYSIS")
            print(f"Date range: {oldest.strftime('%Y-%m-%d')} to {newest.strftime('%Y-%m-%d')}")
            print(f"Span: {(newest - oldest).days} days")
    
    # Title analysis
    titles = [j['title'] for j in jobs if j['title'] != 'N/A']
    print(f"\n💼 TITLE ANALYSIS")
    print(f"Jobs with titles: {len(titles)} ({len(titles)/total_jobs*100:.1f}%)")
    
    # Common keywords in titles
    title_words = []
    for title in titles:
        words = re.findall(r'\b\w+\b', title.lower())
        title_words.extend(words)
    
    word_counts = Counter(title_words)
    common_words = [word for word, count in word_counts.most_common(20) if len(word) > 3]
    
    print(f"Most common words in titles:")
    for word in common_words[:10]:
        count = word_counts[word]
        print(f"  {word}: {count} times")

def analyze_shards(shard_results):
    """Analyze shard performance"""
    print(f"\n\n📈 SHARD PERFORMANCE ANALYSIS")
    print("=" * 50)
    
    total_shards = len(shard_results)
    productive_shards = len([s for s in shard_results.values() if s['job_count'] > 0])
    empty_shards = total_shards - productive_shards
    
    print(f"Total shards: {total_shards}")
    print(f"Productive shards: {productive_shards} ({productive_shards/total_shards*100:.1f}%)")
    print(f"Empty shards: {empty_shards} ({empty_shards/total_shards*100:.1f}%)")
    
    # Experience level analysis
    exp_stats = defaultdict(lambda: {'total': 0, 'jobs': 0})
    for shard in shard_results.values():
        exp = shard['exp_level']
        exp_stats[exp]['total'] += 1
        exp_stats[exp]['jobs'] += shard['job_count']
    
    print(f"\n👥 EXPERIENCE LEVEL ANALYSIS")
    exp_labels = {"1": "Intern", "2": "Entry", "3": "Associate", "4": "Mid-Senior", "5": "Director", "6": "Executive"}
    for exp_code, exp_label in exp_labels.items():
        stats = exp_stats[exp_code]
        avg_jobs = stats['jobs'] / stats['total'] if stats['total'] > 0 else 0
        print(f"  {exp_label}: {stats['jobs']} jobs ({avg_jobs:.1f} avg per shard)")
    
    # Job type analysis
    jt_stats = defaultdict(lambda: {'total': 0, 'jobs': 0})
    for shard in shard_results.values():
        jt = shard['job_type']
        jt_stats[jt]['total'] += 1
        jt_stats[jt]['jobs'] += shard['job_count']
    
    print(f"\n💼 JOB TYPE ANALYSIS")
    jt_labels = {"I": "Internship", "F": "Full-time", "C": "Contract", "T": "Temporary", "P": "Part-time", "V": "Volunteer", "O": "Other"}
    for jt_code, jt_label in jt_labels.items():
        stats = jt_stats[jt_code]
        avg_jobs = stats['jobs'] / stats['total'] if stats['total'] > 0 else 0
        print(f"  {jt_label}: {stats['jobs']} jobs ({avg_jobs:.1f} avg per shard)")
    
    # Workplace type analysis
    wt_stats = defaultdict(lambda: {'total': 0, 'jobs': 0})
    for shard in shard_results.values():
        wt = shard['workplace_type']
        wt_stats[wt]['total'] += 1
        wt_stats[wt]['jobs'] += shard['job_count']
    
    print(f"\n🏢 WORKPLACE TYPE ANALYSIS")
    wt_labels = {"1": "On-site", "2": "Remote", "3": "Hybrid"}
    for wt_code, wt_label in wt_labels.items():
        stats = wt_stats[wt_code]
        avg_jobs = stats['jobs'] / stats['total'] if stats['total'] > 0 else 0
        print(f"  {wt_label}: {stats['jobs']} jobs ({avg_jobs:.1f} avg per shard)")
    
    # Top productive shards
    productive_shards = [(k, v) for k, v in shard_results.items() if v['job_count'] > 0]
    productive_shards.sort(key=lambda x: x[1]['job_count'], reverse=True)
    
    print(f"\n🏆 TOP 10 PRODUCTIVE SHARDS")
    for i, (shard_key, shard_data) in enumerate(productive_shards[:10]):
        print(f"  {i+1}. {shard_data['labels']}: {shard_data['job_count']} jobs")

def analyze_mappings(shard_mappings):
    """Analyze job-to-shard mappings"""
    print(f"\n\n🔗 JOB-TO-SHARD MAPPING ANALYSIS")
    print("=" * 50)
    
    total_jobs = len(shard_mappings)
    jobs_in_multiple_shards = len([j for j in shard_mappings.values() if len(j) > 1])
    
    print(f"Total jobs: {total_jobs}")
    print(f"Jobs found in multiple shards: {jobs_in_multiple_shards} ({jobs_in_multiple_shards/total_jobs*100:.1f}%)")
    
    # Shard overlap analysis
    shard_overlaps = defaultdict(int)
    for job_mappings in shard_mappings.values():
        if len(job_mappings) > 1:
            for mapping in job_mappings:
                shard_overlaps[mapping['shard_key']] += 1
    
    if shard_overlaps:
        print(f"\n📊 SHARDS WITH MOST OVERLAP")
        for shard_key, count in sorted(shard_overlaps.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {shard_key}: {count} overlapping jobs")

def main():
    """Main analysis function"""
    print("🔍 LINKEDIN JOB SCRAPER RESULTS ANALYSIS")
    print("=" * 60)
    
    try:
        jobs, shard_results, shard_mappings = load_data()
        
        analyze_jobs(jobs)
        analyze_shards(shard_results)
        analyze_mappings(shard_mappings)
        
        print(f"\n\n✅ ANALYSIS COMPLETE")
        print("=" * 60)
        
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("Make sure you've run the scraper first!")

if __name__ == "__main__":
    main() 