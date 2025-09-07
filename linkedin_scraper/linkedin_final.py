import sys
import os
import argparse
import subprocess

# Add src and scripts to path for imports
sys.path.append('src')
sys.path.append('scripts')

def main():
    """Main pipeline with configurable search strategies"""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='LinkedIn Job Scraper Pipeline')
    parser.add_argument('--mode', choices=['daily', 'weekly'], default='daily',
                       help='Scraping mode: daily (incremental) or weekly (comprehensive)')
    parser.add_argument('--skip-login', action='store_true',
                       help='Skip login step (use existing cookies)')
    parser.add_argument('--skip-migration', action='store_true',
                       help='Skip database migration step')
    parser.add_argument('--export-tableau', action='store_true',
                       help='Export data for Tableau dashboards')
    
    args = parser.parse_args()
    
    print(f"🚀 Starting LinkedIn pipeline in {args.mode} mode")
    
    # Step 1: Login (unless skipped)
    if not args.skip_login:
        print("📝 Step 1: LinkedIn Login")
        try:
            import login
            login.main()
        except Exception as e:
            print(f"❌ Login failed: {e}")
            print("💡 You can skip login with --skip-login if you have valid cookies")
            return
    else:
        print("⏭️ Skipping login (using existing cookies)")
    
    # Step 2: Scrape with mode-specific settings
    print(f"🔄 Step 2: Job Scraping ({args.mode} mode)")
    try:
        subprocess.run(['python', 'src/linkedin_scraper.py', '--mode', args.mode], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Scraping failed: {e}")
        return
    except FileNotFoundError:
        print("❌ linkedin_scraper.py not found in src/ directory")
        return
    
    # Step 3: Migrate to Database (unless skipped)
    if not args.skip_migration:
        print("💾 Step 3: Database Migration")
        try:
            import migrate_to_db
            migrate_to_db.migrate_jobs()
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            print("💡 You can skip migration with --skip-migration")
            return
    else:
        print("⏭️ Skipping database migration")
    
    # Step 4: Export for Tableau (if requested)
    if args.export_tableau:
        print("📊 Step 4: Tableau Export")
        try:
            import export_for_tableau
            export_for_tableau.main()
        except Exception as e:
            print(f"❌ Tableau export failed: {e}")
            print("💡 You can skip Tableau export by removing --export-tableau")
            return
    else:
        print("⏭️ Skipping Tableau export")
    
    print(f"🎉 Pipeline completed in {args.mode} mode")
    print(f"📊 Data saved to: data/linkedin_jobs_simplified.json")

if __name__ == "__main__":
    main()
