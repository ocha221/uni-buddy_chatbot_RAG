# cli/commands.py
import click
import logging
from services.course_service import CourseService
from services.professor_service import ProfessorService
from services.name_service import NameService
from services.nlp_service import NLPService
from db.collections import Collections

logger = logging.getLogger(__name__)

@click.group()
def cli():
    """University Information System CLI"""
    pass

# Initialize services
collections = Collections()
nlp_service = NLPService()
name_service = NameService(collections, nlp_service)
course_service = CourseService(collections)
professor_service = ProfessorService(collections, name_service)

# Set up service references
professor_service.set_course_service(course_service)
course_service.set_professor_service(professor_service)

@cli.command()
@click.argument('directory', type=click.Path(exists=True))
@click.option('--skip-professors', is_flag=True, help='Skip professor data processing')
def import_courses(directory, skip_professors):
    """Import courses from a directory"""
    count = course_service.batch_import_courses(directory, skip_professors)
    click.echo(f"Imported {count} courses from {directory}")

@cli.command()
def rebuild_professors():
    """Rebuild professor data from courses"""
    count = professor_service.rebuild_professor_data()
    click.echo(f"Rebuilt {count} professor-course relationships")

@cli.command()
@click.option('--interactive', is_flag=True, help='Run in interactive mode')
def consolidate_names(interactive):
    """Consolidate professor names"""
    count = professor_service.consolidate_professor_names(interactive)
    click.echo(f"Created {count} consolidated professor entries")

@cli.command()
@click.argument('query')
def search(query):
    """Search courses by content"""
    results = course_service.search_courses(query, 5)
    if not results or len(results["ids"][0]) == 0:
        click.echo("No results found")
        return
        
    for i, doc_id in enumerate(results["ids"][0]):
        click.echo(f"Result {i+1}: {doc_id}")
        click.echo(f"Metadata: {results['metadatas'][0][i]}")
        click.echo(f"Document excerpt: {results['documents'][0][i][:150]}...\n")

@cli.command()
@click.argument('professor_name')
def professor_courses(professor_name):
    """List courses taught by a professor"""
    courses = professor_service.get_courses_by_professor(professor_name)
    
    if not courses:
        click.echo(f"No courses found for professor '{professor_name}'")
        return
        
    canonical_name = name_service.find_canonical_name(professor_name) or professor_name
    
    click.echo(f"\nCourses taught by {canonical_name}:")
    click.echo("-" * 40)
    
    for course in courses:
        if course["metadata"]:
            click.echo(f"Course: {course['metadata'].get('title', 'Unknown')} ({course['course_code']})")
            click.echo(
                f"Year: {course['metadata'].get('year', 'Unknown')}, " +
                f"Semester: {course['metadata'].get('semester', 'Unknown')}"
            )
        else:
            click.echo(f"Course: {course['course_code']} (details not available)")
        click.echo("-" * 40)

@cli.command()
def interactive():
    """Start interactive query mode"""
    name_service.load_name_cache()
    
    click.echo("\n=== COLLECTION STATISTICS ===")
    click.echo(f"Course collection has {course_service.course_collection.count()} documents")
    click.echo(f"Professor collection has {professor_service.professor_collection.count()} documents")
    click.echo(f"Professor name mappings collection has {name_service.professor_names_collection.count()} documents")
    click.echo(f"Professor name cache has {len(name_service.name_cache)} mappings")
    
    click.echo("\n=== INTERACTIVE QUERY MODE ===")
    click.echo("Enter queries or commands ('exit' to quit):")
    click.echo("- To search by content: 'search: your query'")
    click.echo("- To filter by semester: 'semester: number'")
    click.echo("- To filter by year: 'year: number'")
    click.echo("- To find courses by professor: 'professor: name'")
    click.echo("- For smart professor search: 'find professor: query about a professor'")
    click.echo("- To add a professor name variation: 'add_variation'")
    
    while True:
        user_input = input("\nQuery> ")
        if user_input.lower() == "exit":
            name_service.save_name_cache()
            break
            
        if user_input.startswith("search:"):
            query = user_input[7:].strip()
            results = course_service.search_courses(query)
            _print_results(results)
        elif user_input.startswith("semester:"):
            try:
                semester = int(user_input[9:].strip())
                results = course_service.filter_courses({"semester": semester}, 12)
                _print_results(results)
            except ValueError:
                click.echo("Please enter a valid semester number")
        elif user_input.startswith("year:"):
            try:
                year = int(user_input[5:].strip())
                results = course_service.filter_courses({"year": year}, 27)
                _print_results(results)
            except ValueError:
                click.echo("Please enter a valid year number")
        elif user_input.startswith("professor:"):
            professor_name = user_input[10:].strip()
            _print_professor_courses(professor_name)
        elif user_input.lower().startswith("find professor:"):
            query = user_input[15:].strip()
            click.echo(f"Analyzing query: '{query}'")
            extracted_name = nlp_service.extract_professor_name(query)
            
            if extracted_name:
                click.echo(f"Found professor name: '{extracted_name}'")
                _print_professor_courses(extracted_name)
            else:
                click.echo("No professor name found in your query.")
                click.echo("Try being more specific about the professor you're looking for.")
        elif user_input.lower() == "add_variation":
            _add_manual_professor_variation()
        else:
            # Try to extract professor name from general query
            extracted_name = nlp_service.extract_professor_name(user_input)
            if extracted_name:
                click.echo(f"Detected professor name: '{extracted_name}'. Showing courses:")
                _print_professor_courses(extracted_name)
            else:
                click.echo("Unrecognized command format. Try 'search:', 'semester:', 'year:', 'professor:', 'find professor:', or 'add_variation'")

def _print_results(results):
    """Helper function to print search results"""
    if not results or len(results["ids"][0]) == 0:
        click.echo("No results found")
        return
        
    for i, doc_id in enumerate(results["ids"][0]):
        click.echo(f"Result {i+1}: {doc_id}")
        click.echo(f"Metadata: {results['metadatas'][0][i]}")
        click.echo(f"Document excerpt: {results['documents'][0][i][:150]}...\n")

def _print_professor_courses(professor_name):
    """Helper function to print professor courses"""
    courses = professor_service.get_courses_by_professor(professor_name)
    
    if not courses:
        click.echo(f"No courses found for professor '{professor_name}'")
        return
        
    canonical_name = name_service.find_canonical_name(professor_name) or professor_name
    
    click.echo(f"\nCourses taught by {canonical_name}:")
    click.echo("-" * 40)
    
    for course in courses:
        if course["metadata"]:
            click.echo(f"Course: {course['metadata'].get('title', 'Unknown')} ({course['course_code']})")
            click.echo(
                f"Year: {course['metadata'].get('year', 'Unknown')}, " +
                f"Semester: {course['metadata'].get('semester', 'Unknown')}"
            )
        else:
            click.echo(f"Course: {course['course_code']} (details not available)")
        click.echo("-" * 40)

def _add_manual_professor_variation():
    """Helper function to add a professor name variation"""
    click.echo("\n=== ADD PROFESSOR NAME VARIATION ===")
    click.echo("This will add a new name variation for a professor")
    
    # List all canonical professor names
    all_professors = professor_service.professor_collection.get()
    if not all_professors["ids"]:
        click.echo("No professors found in database!")
        return
        
    click.echo("\nAvailable professors:")
    professors = []
    for i, prof_id in enumerate(all_professors["ids"]):
        if "professor_name" in all_professors["metadatas"][i]:
            name = all_professors["metadatas"][i]["professor_name"]
            professors.append(name)
            click.echo(f"{len(professors)}: {name}")
    
    try:
        choice = int(input("\nSelect a professor number (0 to cancel): "))
        if choice <= 0 or choice > len(professors):
            click.echo("Operation cancelled")
            return
            
        canonical_name = professors[choice - 1]
        variation = input(f"Enter a name variation for {canonical_name}: ")
        
        if variation and name_service.add_name_variation(canonical_name, variation):
            click.echo(f"Added variation '{variation}' for '{canonical_name}'")
            name_service.save_name_cache()
        else:
            click.echo("Failed to add variation")
            
    except ValueError:
        click.echo("Invalid selection")
    except Exception as e:
        click.echo(f"Error: {str(e)}")

if __name__ == "__main__":
    cli()