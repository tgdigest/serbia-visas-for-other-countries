import logging
from pathlib import Path

from .models import Chat, Config, QuestionCategorizationResult, CategorizedQuestion
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

        year_stats = []
        for year in sorted(by_year.keys(), reverse=True):
            months = sorted(by_year[year])
            approved = 0
            rejected = 0
            months_data = []

            for month in months:
                month_data = store.cases.get_month(month)
                approved += month_data.count_approved()
                rejected += month_data.count_rejected()

                cases_with_links = []
                for case in month_data.cases:
                    case_dict = case.model_dump()
                    case_dict['message_links'] = case.summary.get_message_links(chat)
                    cases_with_links.append(case_dict)

                months_data.append({'month': month, 'cases': cases_with_links})

            year_stats.append({'year': year, 'approved': approved, 'rejected': rejected})

            year_template = self.jinja_env.get_template('hugo/cases-year.md.j2')
            self._save(self.output_dir / chat.slug / 'cases' / f'{year}.md', year_template.render(
                months=months_data,
                year=year,
            ))

        index_template = self.jinja_env.get_template('hugo/cases-index.md.j2')
        self._save(
            self.output_dir / chat.slug / 'cases' / '_index.md',
            index_template.render(years=year_stats),
        )

    def _build_faq(self, store: ChatStore, chat: Chat):
        all_categorized = store.categorized_questions.get_all_categorized()

        date_specific = {cat_q.question for cat_q in all_categorized if cat_q.is_date_specific}
        all_with_answers = {q.question for q in store.questions.get_all_questions()} - date_specific
        all_categorized_non_date = {cat_q.question for cat_q in all_categorized if not cat_q.is_date_specific}

        if missing := all_with_answers - all_categorized_non_date:
            missing_list = '\n'.join(f'{i}. {q}' for i, q in enumerate(sorted(missing), 1))
            msg = f'Categorization missing {len(missing)} questions:\n{missing_list}\n\nRun: make categorize-questions'
            raise ValueError(msg)

        index_template = self.jinja_env.get_template('hugo/faq-index.md.j2')
        self._save(self.output_dir / chat.slug / 'faq' / '_index.md', index_template.render(
            categories=self.config.faq_categories,
        ))

        grouped_by_category = self._group_by_category(all_categorized, chat, store)
        category_template = self.jinja_env.get_template('hugo/faq-category.md.j2')
        for weight, category in enumerate(self.config.faq_categories, start=1):
            if category.slug in grouped_by_category:
                by_letter = {}
                for q in sorted(grouped_by_category[category.slug], key=lambda q: q['question']):
                    letter = q['question'][0].upper()
                    by_letter.setdefault(letter, []).append(q)

                self._save(self.output_dir / chat.slug / 'faq' / f'{category.slug}.md', category_template.render(
                    category=category,
                    weight=weight,
                    letter_groups=sorted(by_letter.items()),
                ))

    def _group_by_category(self, all_categorized: list[CategorizedQuestion], chat: Chat, store: ChatStore):
        grouped_by_category = {}
        question_answers = {}

        for q in all_categorized:
            if q.is_date_specific:
                self.logger.debug(f'Skipping date-specific question: `%s` in category `%s`', q.question, q.category_slug)
                continue

            answers_with_links = store.questions.get_all_answers_for_question(q.question, chat)
            if not answers_with_links:
                self.logger.warning(f'No answers for question: `%s` in category `%s`', q.question, q.category_slug)
                continue

            normalized_question = store.normalized_faq.normalize_question(q.category_slug, q.question)
            if normalized_question != q.question:
                self.logger.info(f'Normalized question: `%s` -> `%s` in category `%s`', q.question, normalized_question, q.category_slug)

            question_answers.setdefault(normalized_question, {
                'question': normalized_question,
                'category_slug': q.category_slug,
                'answers_with_links': [],
            })
            question_answers[normalized_question]['answers_with_links'].extend(answers_with_links)
            question_answers[normalized_question]['answers_with_links'] = sorted(
                set(question_answers[normalized_question]['answers_with_links']),
                key=lambda a: a.sort_key
            )

        for data in question_answers.values():
            grouped_by_category.setdefault(data.pop('category_slug'), []).append(data)

        return grouped_by_category

    def _save(self, path: Path, output: str):
        self.logger.info('Save %s...', path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding='utf-8')
