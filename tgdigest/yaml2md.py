import logging
from pathlib import Path

from .models import CategorizedQuestion, Chat, Config
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

        years = self._get_available_years(store) if chat.cases else []
        self._build_section_index(chat, years)

        if chat.cases:
            self._build_cases(store, chat)

        if chat.faq.enabled:
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
        if chat.faq.has_categories():
            self._build_faq_with_categories(store, chat)
        else:
            self._build_faq_without_categories(store, chat)

    def _build_faq_with_categories(self, store: ChatStore, chat: Chat):
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
            categories=chat.faq.categories,
        ))

        grouped_by_category = self._group_by_category(all_categorized, chat, store)
        category_template = self.jinja_env.get_template('hugo/faq-category.md.j2')
        for weight, category in enumerate(chat.faq.categories, start=1):
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

    def _build_faq_without_categories(self, store: ChatStore, chat: Chat):
        all_questions = [q.question for q in store.questions.get_all_questions()]
        questions_with_answers = self._collect_question_answers(all_questions, None, chat, store)

        by_letter = {}
        for data in questions_with_answers:
            letter = data['question'][0].upper()
            by_letter.setdefault(letter, []).append(data)

        category_template = self.jinja_env.get_template('hugo/faq-category.md.j2')
        self._save(self.output_dir / chat.slug / 'faq' / '_index.md', category_template.render(
            category=None,
            weight=1,
            letter_groups=sorted(by_letter.items()),
        ))

    def _collect_question_answers(self, questions_iter, category_slug, chat, store):
        """Collect and normalize question-answer pairs."""
        question_answers = {}

        for question_text in questions_iter:
            answers_with_links = store.questions.get_all_answers_for_question(question_text, chat)
            if not answers_with_links:
                continue

            normalized_question = store.normalized_faq.normalize_question(category_slug, question_text)

            question_answers.setdefault(normalized_question, {
                'question': normalized_question,
                'answers_with_links': [],
            })
            question_answers[normalized_question]['answers_with_links'].extend(answers_with_links)
            question_answers[normalized_question]['answers_with_links'] = sorted(
                set(question_answers[normalized_question]['answers_with_links']),
                key=lambda a: a.sort_key
            )

        return list(question_answers.values())

    def _group_by_category(self, all_categorized: list[CategorizedQuestion], chat: Chat, store: ChatStore):
        by_category = {}

        for q in all_categorized:
            if q.is_date_specific:
                self.logger.debug('Skipping date-specific question: `%s` in category `%s`', q.question, q.category_slug)
                continue
            by_category.setdefault(q.category_slug, []).append(q.question)

        grouped_by_category = {}
        for category_slug, questions in by_category.items():
            grouped_by_category[category_slug] = self._collect_question_answers(
                questions, category_slug, chat, store
            )

        return grouped_by_category

    def _save(self, path: Path, output: str):
        self.logger.info('Save %s...', path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding='utf-8')
