import logging
from pathlib import Path

from .models import Chat, Config
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
        years = sorted(set(m.year for m in all_months), reverse=True)
        return years

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
        all_months = store.questions.get_all_months()
        if not all_months:
            self.logger.info('No questions found for %s', chat.slug)
            return

        all_questions = []
        for month in all_months:
            month_data = store.questions.get_month(month)
            for question in month_data.questions:
                if not question.answers:
                    continue

                q_dict = question.model_dump()
                q_dict['answers_with_links'] = []

                for answer in question.answers:
                    answer_dict = answer.model_dump()
                    answer_dict['message_links'] = answer.get_message_links(chat)
                    q_dict['answers_with_links'].append(answer_dict)

                all_questions.append(q_dict)

        all_questions.sort(key=lambda q: q['question'])

        grouped = {}
        for q in all_questions:
            section = q['question'][0].upper()
            if section not in grouped:
                grouped[section] = []
            grouped[section].append(q)

        template = self.jinja_env.get_template('hugo/faq.md.j2')
        self._save(self.output_dir / chat.slug / 'faq.md', template.render(
            groups=sorted(grouped.items()),
        ))

    def _save(self, path: Path, output: str):
        self.logger.info('Save %s...', path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding='utf-8')
