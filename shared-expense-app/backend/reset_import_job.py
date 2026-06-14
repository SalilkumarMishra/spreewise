import os
import django
import sys

# Setup Django context
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from imports.models import ImportJob

def list_jobs():
    jobs = ImportJob.objects.all().order_by("-created_at")
    if not jobs.exists():
        print("No Import Jobs found.")
        return []
    print("\n--- Current Import Jobs ---")
    for j in jobs:
        print(f"ID: {j.id} | Filename: {j.original_filename} | Status: {j.status} | Created: {j.created_at}")
    return jobs

def delete_job(job_id):
    try:
        job = ImportJob.objects.get(id=job_id)
        filename = job.original_filename
        job.delete()
        print(f"SUCCESS: ImportJob ID {job_id} ('{filename}') and all associated rows, anomalies, decisions, and reports have been deleted.")
    except ImportJob.DoesNotExist:
        print(f"ERROR: ImportJob ID {job_id} does not exist.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1].lower() == "all":
            count = ImportJob.objects.count()
            ImportJob.objects.all().delete()
            print(f"SUCCESS: All {count} ImportJobs and related records deleted.")
        else:
            try:
                job_id = int(sys.argv[1])
                delete_job(job_id)
            except ValueError:
                print("Usage: python reset_import_job.py [job_id | all]")
    else:
        list_jobs()
        print("\nUsage: python reset_import_job.py [job_id | all]")
