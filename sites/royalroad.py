#!/usr/bin/python

import http.client
import logging
import datetime
import re
from . import register, Site, Section, Chapter, SiteSpecificOption

logger = logging.getLogger(__name__)


@register
class RoyalRoad(Site):
    domain = r'royalroad'

    @staticmethod
    def get_site_specific_option_defs():
        return Site.get_site_specific_option_defs() + [
            SiteSpecificOption(
                'skip_spoilers',
                '--skip-spoilers/--include-spoilers',
                default=True,
                help="If true, do not transcribe any tags that are marked as a spoiler."
            ),
            SiteSpecificOption(
                'offset',
                '--offset',
                type=int,
                help="The chapter index to start in the chapter marks."
            ),
            SiteSpecificOption(
                'limit',
                '--limit',
                type=int,
                help="The chapter to end at at in the chapter marks."
            ),
        ]

    """Royal Road: a place where people write novels, mostly seeming to be light-novel in tone."""
    @classmethod
    def matches(cls, url):
        # e.g. https://royalroad.com/fiction/6752/lament-of-the-fallen
        match = re.match(r'^(https?://(?:www\.)?%s\.com/fiction/\d+)/?.*' % cls.domain, url)
        if match:
            return match.group(1) + '/'

    def extract(self, url):
        workid = re.match(r'^https?://(?:www\.)?%s\.com/fiction/(\d+)/?.*' % self.domain, url).group(1)
        soup = self._soup(f'https://www.{self.domain}.com/fiction/{workid}')
        # should have gotten redirected, for a valid title

        base = soup.head.base and soup.head.base.get('href') or url

        original_maxheaders = http.client._MAXHEADERS
        http.client._MAXHEADERS = 1000

        story = Section(
            title=soup.find('h1').string.strip(),
            author=soup.find('meta', property='books:author').get('content').strip(),
            url=soup.find('meta', property='og:url').get('content').strip(),
            cover_url=self._join_url(base, soup.find('img', class_='thumbnail')['src']),
            summary=str(soup.find('div', class_='description')).strip(),
            tags=[tag.get_text().strip() for tag in soup.select('span.tags a.fiction-tag')]
        )

        for index, chapter in enumerate(soup.select('#chapters tbody tr[data-url]')):
            if self.options['offset'] and index < self.options['offset']:
                continue
            if self.options['limit'] and index >= self.options['limit']:
                continue
            chapter_url = str(self._join_url(story.url, str(chapter.get('data-url'))))

            contents, updated = self._chapter(chapter_url, len(story) + 1)

            story.add(Chapter(title=chapter.find('a', href=True).string.strip(), contents=contents, date=updated))

        http.client._MAXHEADERS = original_maxheaders

        story.footnotes = self.footnotes
        self.footnotes = []

        return story

    def _chapter(self, url, chapterid):
        logger.info("Extracting chapter @ %s", url)
        soup = self._soup(url)
        content = soup.find('div', class_='chapter-content')

        self._clean(content, soup)
        self._clean_spoilers(content, chapterid)

        content = str(content)

        author_note = soup.find_all('div', class_='author-note-portlet')

        if len(author_note) == 1:
            # Find the parent of chapter-content and check if the author's note is the first child div
            if 'author-note-portlet' in soup.find('div', class_='chapter-content').parent.find('div')['class']:
                content = str(author_note[0]) + '<hr/>' + content
            else:  # The author note must be after the chapter content
                content = content + '<hr/>' + str(author_note[0])
        elif len(author_note) == 2:
            content = str(author_note[0]) + '<hr/>' + content + '<hr/>' + str(author_note[1])

        updated = datetime.datetime.fromtimestamp(
            int(soup.find(class_="profile-info").find('time').get('unixtime'))
        )

        return content, updated

    def _clean(self, contents, full_page):
        contents = super()._clean(contents)

        # Royalroad has started inserting "this was stolen" notices into its
        # HTML, and hiding them with CSS. Currently the CSS is very easy to
        # find, so do so and filter them out.
        for style in full_page.find_all('style'):
            if m := re.match(r'\s*\.(\w+)\s*{[^}]*display:\s*none;[^}]*}', style.string):
                for warning in contents.find_all(class_=m.group(1)):
                    warning.decompose()

        return contents

    def _clean_spoilers(self, content, chapterid):
     # Display spoilers inline without spoiler tags, and just add a spoiler header
     for spoiler in content.find_all(class_='spoiler'):
        spoiler_title = spoiler.find('div', class_='smalltext').get_text(strip = True)
        if (not spoiler_title):
            spoiler_title = ' '
        spoiler_header = '[SPOILER - ' + spoiler_title + ']'
        spoiler_header_tag = self._new_tag('strong', class_='spoiler-header')
        spoiler_header_tag.string = spoiler_header

        # Locate the spoiler content div
        spoiler_content = spoiler.find('div', class_='spoilerContent')
        if spoiler_content:
            spoiler_inner = spoiler_content.find('div', class_='spoiler-inner')
            if spoiler_inner:
                # Insert the spoiler header before the spoiler content
                spoiler.insert_before(spoiler_header_tag)
                spoiler_header_tag.insert_after(spoiler_inner)
                spoiler_inner['style'] = ''

                # Remove the spoiler wrapper and other unnecessary elements
                for tag_to_remove in spoiler.find_all(['div', 'input']):
                    tag_to_remove.extract()

                # Remove the remaining spoiler div
                spoiler.extract()


@register
class RoyalRoadL(RoyalRoad):
    domain = 'royalroadldl'
