from backend.core.constants import JobStatus
from backend.repositories.application_repository import ApplicationRepository
from backend.repositories.interview_preparation_repository import (
    InterviewPreparationRepository,
)
from backend.repositories.job_repository import JobRepository
from backend.repositories.resume_optimization_repository import (
    ResumeOptimizationRepository,
)
from backend.schemas.dashboard import (
    DashboardJobItem,
    DashboardRecentJob,
    DashboardStageSummary,
    DashboardSummaryResponse,
    DashboardTodoItem,
)


class DashboardService:
    PENDING_STATUSES = {
        JobStatus.SAVED.value,
        JobStatus.PLANNED.value,
    }
    ASSESSMENT_INTERVIEW_STATUSES = {
        JobStatus.WRITTEN_TEST.value,
        JobStatus.INTERVIEW_1.value,
        JobStatus.INTERVIEW_2.value,
    }

    def __init__(
        self,
        job_repository: JobRepository,
        application_repository: ApplicationRepository,
        resume_repository: ResumeOptimizationRepository,
        interview_repository: InterviewPreparationRepository,
    ) -> None:
        self._jobs = job_repository
        self._applications = application_repository
        self._resumes = resume_repository
        self._interviews = interview_repository

    def get_summary(self) -> DashboardSummaryResponse:
        jobs = self._jobs.list()
        queue = self._applications.list()
        resume_job_ids = self._resumes.list_job_ids()
        interview_job_ids = self._interviews.list_job_ids()

        status_counts = {
            status.value: sum(job.status == status.value for job in jobs)
            for status in JobStatus
        }
        saved_planned_count = sum(
            status_counts[status] for status in self.PENDING_STATUSES
        )
        assessment_interview_count = sum(
            status_counts[status]
            for status in self.ASSESSMENT_INTERVIEW_STATUSES
        )
        pending_queue_count = sum(
            item.status in self.PENDING_STATUSES for item in queue
        )
        average_match_score = (
            sum(job.match_score for job in jobs) / len(jobs)
            if jobs
            else 0.0
        )

        pending_jobs = [
            job for job in jobs if job.status in self.PENDING_STATUSES
        ]
        priority_jobs = sorted(
            pending_jobs,
            key=lambda job: (job.match_score, job.id),
            reverse=True,
        )[:5]
        recent_jobs = sorted(
            jobs,
            key=lambda job: (job.updated_at or job.created_at, job.id),
            reverse=True,
        )[:10]

        todos = [
            DashboardTodoItem(
                key="pending_without_resume",
                label="待投递但尚未生成简历优化",
                count=sum(
                    job.id not in resume_job_ids for job in pending_jobs
                ),
            ),
            DashboardTodoItem(
                key="pending_without_interview",
                label="待投递但尚未生成面试准备",
                count=sum(
                    job.id not in interview_job_ids for job in pending_jobs
                ),
            ),
            DashboardTodoItem(
                key="applied_without_interview",
                label="已投递但尚未生成面试准备",
                count=sum(
                    job.status == JobStatus.APPLIED.value
                    and job.id not in interview_job_ids
                    for job in jobs
                ),
            ),
            DashboardTodoItem(
                key="active_follow_up",
                label="笔试或面试阶段需要继续跟进",
                count=assessment_interview_count,
            ),
        ]

        stages = DashboardStageSummary(
            saved_planned=saved_planned_count,
            applied=status_counts[JobStatus.APPLIED.value],
            assessment_interview=assessment_interview_count,
            offer=status_counts[JobStatus.OFFER.value],
            rejected=status_counts[JobStatus.REJECTED.value],
            abandoned=status_counts[JobStatus.ABANDONED.value],
        )
        return DashboardSummaryResponse(
            saved_planned_count=saved_planned_count,
            pending_queue_count=pending_queue_count,
            applied_count=status_counts[JobStatus.APPLIED.value],
            assessment_interview_count=assessment_interview_count,
            offer_count=status_counts[JobStatus.OFFER.value],
            rejected_count=status_counts[JobStatus.REJECTED.value],
            abandoned_count=status_counts[JobStatus.ABANDONED.value],
            average_match_score=round(average_match_score, 1),
            stages=stages,
            priority_jobs=[self._job_item(job) for job in priority_jobs],
            todos=todos,
            recent_jobs=[
                DashboardRecentJob(
                    **self._job_item(job).model_dump(),
                    created_at=job.created_at,
                    updated_at=job.updated_at or job.created_at,
                )
                for job in recent_jobs
            ],
        )

    @staticmethod
    def _job_item(job) -> DashboardJobItem:
        return DashboardJobItem(
            id=job.id,
            company=job.company,
            position=job.position,
            match_score=job.match_score,
            status=job.status,
            job_url=job.job_url,
        )
