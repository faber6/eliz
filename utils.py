from difflib import SequenceMatcher
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained('gpt2')

TRIM_DIR_TOP = 0
TRIM_DIR_BOTTOM = 1
TRIM_DIR_NONE = 2

TRIM_TYPE_NEWLINE = 3
TRIM_TYPE_SENTENCE = 4
TRIM_TYPE_TOKEN = 5

INSERTION_TYPE_NEWLINE = 6
INSERTION_TYPE_SENTENCE = 7
INSERTION_TYPE_TOKEN = 8


def anti_spam(messages, threshold=0.8):
    to_remove = []
    for i in range(len(messages)):
        for j in range(i+1, len(messages)):
            if i != j:
                if SequenceMatcher(None, messages[i].content, messages[j].content).ratio() > threshold:
                    to_remove.append(j)
    to_remove = list(set(to_remove))
    messages = [messages[i]
                for i in range(len(messages)) if i not in to_remove]
    return messages, len(to_remove)


def standardize_punctuation(text):
    text = text.replace("’", "'")
    text = text.replace("`", "'")
    text = text.replace("“", '"')
    text = text.replace("”", '"')
    return text


def fix_trailing_quotes(text):
    num_quotes = text.count('"')
    if num_quotes % 2 == 0:
        return text
    else:
        return text + '"'


def cut_trailing_sentence(text):
    text = standardize_punctuation(text)
    last_punc = max(text.rfind("."), text.rfind("!"), text.rfind("?"), text.rfind(".\""), text.rfind(
        "!\""), text.rfind("?\""), text.rfind(".\'"), text.rfind("!\'"), text.rfind("?\'"))
    if last_punc <= 0:
        last_punc = len(text) - 1
    et_token = text.find("<")
    if et_token > 0:
        last_punc = min(last_punc, et_token - 1)
    text = text[: last_punc + 1]
    text = fix_trailing_quotes(text)
    return text


class Preprocessor:
    """Abstract class for preprocessors.
    """

    def __call__(self, context: str, is_respond: bool, name: str) -> str:
        """Process the given context before the ModelProvider is called.

        :param context: The context to preprocess.
        :type context: str
        :param is_respond: Whether the context is being built for a chatbot response.
        :type is_respond: bool
        :param name: The name of the chatbot.
        :type name: str
        :return: The processed context.
        :rtype: str
        """
        raise NotImplementedError(f'{self.__class__} is an abstract class')


class ContextPreprocessor(Preprocessor):
    """A Preprocessor that builds a context from a list of ContextEntry objects."""

    def __init__(self, token_budget=1024):
        """Initialize a ContextPreprocessor.

        :param token_budget: The maximum number of tokens that can be used in the context, defaults to 1024.
        :type token_budget: int, optional
        """
        self.token_budget = token_budget
        self.entries = []

    def add_entry(self, entry):
        """Add a ContextEntry to the ContextPreprocessor.

        :param entry: The ContextEntry to add.
        :type entry: ContextEntry
        """
        self.entries.append(entry)

    def del_entry(self, entry):
        """Delete a ContextEntry from the ContextPreprocessor.

        :param entry: The ContextEntry to delete.
        :type entry: ContextEntry
        """
        self.entries.remove(entry)

    # return true if key is found in an entry's text
    def key_lookup(self, entry_a, entry_b):
        """Check if a ContextEntry's key is found in an entry's text.

        :param entry_a: The ContextEntry to check.
        :type entry_a: ContextEntry
        :param entry_b: Another ContextEntry to check.
        :type entry_b: ContextEntry
        :return: Whether the key is found in the text.
        :rtype: bool
        """
        for i in entry_b.keys:
            if i == '':
                continue
            if i.lower() in entry_a.text.lower():
                return True
        return False

    # recursive function that searches for other entries that are activated
    def cascade_lookup(self, entry, nest=0):
        """Search for other entries that are activated by a given entry.

        :param entry: The entry to recursively search for other entries in.
        :type entry: ContextEntry
        :param nest: The maximum amount of recursion to perform, defaults to 0.
        :type nest: int, optional
        :return: A list of other entries that are activated by the given entry.
        :rtype: list
        """
        cascaded_entries = []
        if nest > 3:
            return []
        for i in self.entries:
            if self.key_lookup(entry, i):
                # check if i activates entry to prevent infinite loop
                if self.key_lookup(i, entry):
                    cascaded_entries.append(i)
                    continue
                for j in self.cascade_lookup(i, nest+1):
                    cascaded_entries.append(j)
        return cascaded_entries

    # handles cases where elements are added to the end of a list using list.insert
    def ordinal_pos(self, position, length):
        if position < 0:
            return length + 1 + position
        return position

    def context(self, budget=1024):
        """Build the context from the ContextPreprocessor's entries.

        :param budget: The maximum number of tokens that can be used in the context, defaults to 1024.
        :type budget: int, optional
        :return: The built context.
        :rtype: str
        """
        # sort self.entries by insertion_order
        self.entries.sort(key=lambda x: x.insertion_order, reverse=True)
        activated_entries = []

        # Get entries activated by default
        for i in self.entries:
            if i.forced_activation:
                if i.cascading_activation:
                    for j in self.cascade_lookup(i):
                        activated_entries.append(j)
                    activated_entries.append(i)
                else:
                    activated_entries.append(i)
            if i.insertion_position > 0 or i.insertion_position < 0:
                if i.reserved_tokens == 0:
                    i.reserved_tokens = len(tokenizer.encode(i.text))

        activated_entries = list(set(activated_entries))
        # sort activated_entries by insertion_order
        activated_entries.sort(key=lambda x: x.insertion_order, reverse=True)

        newctx = []
        for i in activated_entries:
            reserved = 0
            if i.reserved_tokens > 0:
                len_tokens = len(tokenizer.encode(i.text))
                if len_tokens < i.reserved_tokens:
                    budget -= len_tokens
                else:
                    budget -= i.reserved_tokens
                if len_tokens > i.reserved_tokens:
                    reserved = i.reserved_tokens
                else:
                    reserved = len_tokens

            text = i.get_text(budget + reserved, self.token_budget)
            ctxtext = text.splitlines(keepends=False)
            trimmed_tokenized = tokenizer.encode(text)
            budget -= len(trimmed_tokenized) - reserved
            ctxinsertion = i.insertion_position

            before = []
            after = []

            if i.insertion_position < 0:
                ctxinsertion += 1
                if len(newctx) + ctxinsertion >= 0:
                    before = newctx[0:len(newctx)+ctxinsertion]
                    after = newctx[len(newctx)+ctxinsertion:]
                else:
                    before = []
                    after = newctx[0:]
            else:
                before = newctx[0:ctxinsertion]
                after = newctx[ctxinsertion:]

            newctx = []

            for bIdx in range(len(before)):
                newctx.append(before[bIdx])
            for cIdx in range(len(ctxtext)):
                newctx.append(ctxtext[cIdx])
            for aIdx in range(len(after)):
                newctx.append(after[aIdx])
        return '\n'.join(newctx)

    def __call__(self, context: str, is_respond: bool, name: str) -> str:
        """Build the context from the ContextPreprocessor's entries.

        :param context: The context to build the context from.
        :type context: str
        :param is_respond: Whether the context is being built for a chatbot response.
        :type is_respond: bool
        :param name: The name of the chatbot.
        :type name: str
        :return: The processed context.
        :rtype: str
        """

        if is_respond:
            main_entry = ContextEntry(text=context, suffix=f'\n{name}:', reserved_tokens=512, insertion_order=0, trim_direction=TRIM_DIR_TOP,
                                      forced_activation=True, cascading_activation=True, insertion_type=INSERTION_TYPE_NEWLINE, insertion_position=-1)
        else:
            main_entry = ContextEntry(text=context, suffix='\n', reserved_tokens=512, insertion_order=0, trim_direction=TRIM_DIR_TOP,
                                      forced_activation=True, cascading_activation=True, insertion_type=INSERTION_TYPE_NEWLINE, insertion_position=-1)
        self.add_entry(main_entry)
        constructed_context = self.context()
        self.del_entry(main_entry)
        return constructed_context


def trim_newlines(tokens, trim_dir, limit):
    if (trim_dir == TRIM_DIR_NONE) or (len(tokens) <= limit):
        return tokens

    lines = tokenizer.decode(tokens).split('\n')
    start, end, step = 0, 0, 0
    if trim_dir == TRIM_DIR_TOP:
        start = len(lines) - 1
        end = -1
        step = -1
    elif trim_dir == TRIM_DIR_BOTTOM:
        start = 0
        end = len(lines)
        step = 1

    acc_tokens = []

    for idx in range(start, end, step):
        line = lines[idx]
        if trim_dir == TRIM_DIR_TOP:
            line = '\n' + line
        elif trim_dir == TRIM_DIR_BOTTOM:
            line = line + '\n'
        new_tokens = tokenizer.encode(line)
        if len(new_tokens) + len(acc_tokens) > limit:
            return acc_tokens
        else:
            if trim_dir == TRIM_DIR_TOP:
                acc_tokens = new_tokens + acc_tokens
            elif trim_dir == TRIM_DIR_BOTTOM:
                acc_tokens = acc_tokens + new_tokens
    return acc_tokens


def trim_sentences(tokens, trim_dir, limit):
    if (trim_dir == TRIM_DIR_NONE) or (len(tokens) <= limit):
        return tokens

    text = tokenizer.decode(tokens)
    sentences = split_into_sentences(text)

    start, end, step = 0, 0, 0
    text_begin, text_end = 0, 0
    sentence_idx, last_sentence_idx = 0, 0

    if trim_dir == TRIM_DIR_TOP:
        start = len(sentences) - 1
        end = -1
        step = -1
        text_begin = 0
        text_end = len(text)
    elif trim_dir == TRIM_DIR_BOTTOM:
        start = 0
        end = len(sentences)
        step = 1
        text_begin = 0
        text_end = len(text)
    else:
        return tokens

    for idx in range(start, end, step):
        sentence = sentences[idx]
        if trim_dir == TRIM_DIR_TOP:
            sentence_idx = text.rindex(sentence) + text_begin
            if (sentence_idx > 0) and (sentence_idx < len(text)) and (text[sentence_idx] == ' '):
                sentence_idx -= 1
            to_tokenize = text[sentence_idx:]
            token_count = len(tokenizer.encode(to_tokenize))
            if token_count >= limit:
                to_encode = text[text_end:]
                return tokenizer.encode(to_encode)
            text_end = sentence_idx - 1
        elif trim_dir == TRIM_DIR_BOTTOM:
            sentence_idx = text.index(sentence) + text_begin
            sentence_end = sentence_idx + len(sentence)
            if (sentence_end < text_end) and (text[sentence_end:sentence_end+1] == '\n'):
                sentence_end += 1
            to_tokenize = text[0:sentence_end]
            token_count = len(tokenizer.encode(to_tokenize))
            if token_count >= limit:
                to_encode = text[0:last_sentence_idx]
                return tokenizer.encode(to_encode)
            last_sentence_idx = sentence_end
            text_begin += len(sentence)
    return tokens


def trim_tokens(tokens, trim_dir, limit):
    if (trim_dir == TRIM_DIR_NONE) or (len(tokens) <= limit):
        return tokens
    if trim_dir == TRIM_DIR_TOP:
        return tokens[len(tokens)-limit:]
    elif trim_dir == TRIM_DIR_BOTTOM:
        return tokens[:limit]


class ContextEntry:
    def __init__(self, keys=[''], text='', prefix='', suffix='\n', token_budget=2048, reserved_tokens=0, insertion_order=100, insertion_position=-1, trim_direction=TRIM_DIR_BOTTOM, trim_type=TRIM_TYPE_SENTENCE, insertion_type=INSERTION_TYPE_SENTENCE, forced_activation=False, cascading_activation=False):
        self.keys = keys  # key used to activate this context entry
        self.text = prefix + text + suffix  # text associated with this context entry
        # max amount of tokens that this context entry can use
        self.token_budget = token_budget
        # number of tokens that are reserved for this context entry
        self.reserved_tokens = reserved_tokens
        # order in which this context entry is inserted
        self.insertion_order = insertion_order
        # position in the text where this context entry is inserted, 0 is the beginning, -1 is the end
        self.insertion_position = insertion_position
        self.trim_direction = trim_direction  # direction in which to trim the text
        self.trim_type = trim_type  # type of trimming to perform
        # determines what units are used to insert the text
        self.insertion_type = insertion_type
        # if True, this context entry is activated even if it is not activated
        self.forced_activation = forced_activation
        # when activated, this context entry will search for other entries and activate them if found
        self.cascading_activation = cascading_activation

    # max_length is in tokens
    def trim(self, max_length, token_budget):
        target = 0
        tokens = tokenizer.encode(self.text)
        num_tokens = len(tokens)
        projected = max_length - num_tokens
        if projected > token_budget:
            target = token_budget
        elif projected >= 0:
            target = num_tokens
        else:
            target = max_length
        if self.trim_type == TRIM_TYPE_NEWLINE:
            tokens = trim_newlines(tokens, self.trim_direction, target)
        elif self.trim_type == TRIM_TYPE_SENTENCE or len(tokens) > target:
            tokens = trim_sentences(tokens, self.trim_direction, target)
        elif self.trim_type == TRIM_TYPE_TOKEN or len(tokens) > target:
            tokens = trim_tokens(tokens, self.trim_direction, target)
        return tokens

    def get_text(self, max_length, token_budget):
        return tokenizer.decode(self.trim(max_length, token_budget))
