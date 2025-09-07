import json

def process_cb_insights_2025():
    """Process CB Insights AI 100 2025 list"""
    
    # CB Insights AI 100 2025 companies
    companies_2025 = [
        "1X", "Aaru", "Altera", "Ambience", "Antiverse", "Apptronik", "Arcee", 
        "Archetype AI", "Arize", "Atropos Health", "Auquan", "Binarly", "Bioptimus", 
        "Bland AI", "BrainSightAI", "Braintrust", "Bria", "Browserbase", "Cartesia", 
        "Chainguard", "Chroma", "Cohere", "Credo AI", "DEFCON AI", "Delphina", 
        "Dexory", "ElevenLabs", "Ellipsis Health", "Etched", "EvolutionaryScale", 
        "Exokernel", "Ferrum Health", "Fiddler", "Fixie", "Fwd", "Ganymede", 
        "Gauss Labs", "Genei", "Globus AI", "Greeneye", "Hazy", "Hebbia", 
        "Inflection", "K Health", "KEF Robotics", "Kumo", "Lakera", "LangChain", 
        "Lamini", "LassoMD", "LightOn", "LightOn Labs", "LolliBots", "Meistrari", 
        "Metaplane", "Moonhub", "Moonshot AI", "Moonvalley", "MotherDuck", 
        "Motional", "Nabla", "Neko Health", "Nomic", "OctoAI", "OneSchema", 
        "OpenPipe", "OpenPodcast", "Orby AI", "Pawn AI", "Perplexity", "Phind", 
        "Pixis", "PolyAI", "Predibase", "Primer", "Raycast", "Runway", "Sana", 
        "Seek AI", "Shaped", "Skyfire", "Skyflow", "Slingshot AI", "Snyk", 
        "Spate", "Stellantis AI", "SynthID", "Synthflow", "Tavus", "Twelve Labs", 
        "Tera AI", "ThinkLabs", "Together AI", "Unstructured", "Upstage", 
        "Vijil", "Waabi", "Wayve", "Wordsmith", "World Labs", "Xscape Photonics", 
        "Zama", "aiXplain", "webAI"
    ]
    
    # Remove duplicates and sort
    unique_companies = sorted(list(set(companies_2025)))
    
    # Create data structure
    data = {
        "source": "CB Insights AI 100",
        "year": "2025",
        "count": len(unique_companies),
        "companies": unique_companies
    }
    
    # Save to JSON
    with open('cb_insights_2025.json', 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Processed CB Insights AI 100 2025")
    print(f"📊 Total companies: {len(unique_companies)}")
    print(f"💾 Saved to cb_insights_2025.json")
    
    return unique_companies

if __name__ == "__main__":
    companies = process_cb_insights_2025()
    
    print(f"\n🏢 CB Insights AI 100 2025 Companies:")
    print("=" * 50)
    for i, company in enumerate(companies, 1):
        print(f"{i:2d}. {company}") 