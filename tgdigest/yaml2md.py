import logging
from pathlib import Path

from .models import Chat, Config, QuestionCategorizationResult, ReferencedSummary
from .stores import ChatStore
from .templates import get_jinja_env


class Yaml2Md:
    def __init__(self, config: Config, output_dir: str, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        self.config = config
        self.output_dir = Path(output_dir)
        self.jinja_env = get_jinja_env()

    def process_chat(self, chat: Chat):
        self.logger.info('Building markdown for chat: %s (%s)', chat.title, chat.url)

        store = ChatStore(chat)

        years = self._get_available_years(store)
        self._build_section_index(chat, years)
        self._build_cases(store, chat)
        self._build_faq(store, chat)

    def _get_available_years(self, store: ChatStore) -> list[int]:
        all_months = store.cases.get_all_months()
        return sorted({m.year for m in all_months}, reverse=True)

    def _build_section_index(self, chat: Chat, years: list[int]):
        template = self.jinja_env.get_template('hugo/section-index.md.j2')
        self._save(self.output_dir / chat.slug / '_index.md', template.render(
            chat=chat,
            latest_year=years[0] if years else None,
        ))

    def _build_cases(self, store: ChatStore, chat: Chat):
        all_months = store.cases.get_all_months()
        if not all_months:
            self.logger.info('No cases found for %s', chat.slug)
            return

        by_year = {}
        for month in all_months:
            year = month.year
            if year not in by_year:
                by_year[year] = []
            by_year[year].append(month)

        template = self.jinja_env.get_template('hugo/cases.md.j2')

        for year in sorted(by_year.keys(), reverse=True):
            months = sorted(by_year[year])
            months_data = []

            for month in months:
                month_data = store.cases.get_month(month)
                cases_with_links = []

                for case in month_data.cases:
                    case_dict = case.model_dump()
                    case_dict['message_links'] = case.summary.get_message_links(chat)
                    cases_with_links.append(case_dict)

                months_data.append({'month': month, 'cases': cases_with_links})

            self._save(self.output_dir / chat.slug / f'cases-{year}.md', template.render(
                months=months_data,
                year=year,
            ))

    def _build_faq(self, store: ChatStore, chat: Chat):
        all_categorized = []
        for month in store.categorized_questions.get_all_months():
            month_data = store.categorized_questions.get_month(month)
            all_categorized.extend(month_data.questions)

        categorized = QuestionCategorizationResult(questions=all_categorized)
        question_map = self._build_question_map(store)

        all_questions_in_map = set(question_map)
        all_questions_categorized = {cat_q.question for cat_q in categorized.questions}

        missing = all_questions_in_map - all_questions_categorized
        if missing:
            missing_list = '\n'.join(f'{i}. {q}' for i, q in enumerate(sorted(missing), 1))
            msg = f'Categorization missing {len(missing)} questions:\n{missing_list}\n\nRun: make categorize-questions'
            raise ValueError(msg)

        grouped_by_category = self._group_by_category(categorized, question_map, chat)

        index_template = self.jinja_env.get_template('hugo/faq-index.md.j2')
        self._save(
            self.output_dir / chat.slug / 'faq' / '_index.md',
            index_template.render(categories=self.config.faq_categories),
        )

        category_template = self.jinja_env.get_template('hugo/faq-category.md.j2')
        for cat in self.config.faq_categories:
            if cat.slug in grouped_by_category:
                self._save(
                    self.output_dir / chat.slug / 'faq' / f'{cat.slug}.md',
                    category_template.render(
                        category=cat,
                        questions=grouped_by_category[cat.slug],
                    ),
                )

    def _build_question_map(self, store: ChatStore):
        question_map = {}
        for month in store.questions.get_all_months():
            month_data = store.questions.get_month(month)
            for question in month_data.questions:
                if not question.answers:
                    continue
                if question.question not in question_map:
                    question_map[question.question] = []
                question_map[question.question].append((month, question))
        return question_map

    def _group_by_category(self, categorized, question_map, chat):
        grouped_by_category = {}
        for cat_q in categorized.questions:
            if cat_q.question not in question_map:
                continue

            all_answers = []
            for month, q in question_map[cat_q.question]:
                all_answers.extend((month, answer) for answer in q.answers)

            all_answers.sort(key=lambda x: x[0], reverse=True)

            answers_with_links = [
                ReferencedSummary(
                    text=answer.text,
                    message_ids=answer.message_ids,
                    sender=answer.sender,
                    year=month.year,
                    message_links=answer.get_message_links(chat),
                )
                for month, answer in all_answers
            ]

            grouped_by_category.setdefault(cat_q.category_slug, []).append({
                'question': cat_q.question,
                'answers_with_links': answers_with_links,
            })

        return grouped_by_category

    def _save(self, path: Path, output: str):
        self.logger.info('Save %s...', path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding='utf-8')
