"""
Utility templates to submit in WhatsApp Manager.

Proactive invoice, payment, and result messages are sent outside the
24-hour customer-service window, so Meta only accepts pre-approved
templates. Approval is a manual dashboard step. This module is the text
to submit. Do not create templates from the app.

Category is UTILITY (transactional), language ``en``. Names are what
``WhatsAppNotificationService`` sends. A portal link is a body variable
because each school has its own frontend origin — a URL button would
freeze one host at approval time.

Meta rejects a body that starts or ends with a variable. Parameters
cannot be empty, and a result template has no score, position, or remark
variable. Line items are not a fixed list, so the invoice template
carries the total and the portal link; the itemised bill stays in email
and on /parent/fees.
"""

INVOICE_TEMPLATE_NAME = 'kowe_invoice_generated'
PAYMENT_TEMPLATE_NAME = 'kowe_payment_confirmed'
RESULT_TEMPLATE_NAME = 'kowe_result_published'

TEMPLATE_LANGUAGE = 'en'
TEMPLATE_CATEGORY = 'UTILITY'
TEMPLATE_FOOTER = 'Kowe'

# {{n}} names, in order. The sender fills them in this order.
INVOICE_PARAMETERS = (
    'parent_name',
    'student_name',
    'term_label',
    'school_name',
    'amount_due',
    'portal_url',
)
PAYMENT_PARAMETERS = (
    'parent_name',
    'student_name',
    'term_label',
    'school_name',
    'amount_paid',
    'invoice_total',
    'portal_url',
)
RESULT_PARAMETERS = (
    'parent_name',
    'student_name',
    'term_label',
    'school_name',
    'portal_url',
)

INVOICE_BODY = (
    'Hello {{1}}, a new invoice is ready for {{2}} for {{3}} at {{4}}. '
    'Amount due: {{5}}. Review the invoice and pay from the parent portal: '
    '{{6}}. This is a fee notice from your school.'
)
PAYMENT_BODY = (
    'Hello {{1}}, we received a payment for {{2}} for {{3}} at {{4}}. '
    'Amount paid: {{5}}. Invoice total: {{6}}. Review the invoice in the '
    'parent portal: {{7}}. This is a payment receipt from your school.'
)
RESULT_BODY = (
    'Hello {{1}}, results for {{2}} for {{3}} at {{4}} are now available. '
    'Sign in to the parent portal to view the full report: {{5}}. '
    'Scores are not included in this message.'
)

INVOICE_EXAMPLE = (
    'Chinedu',
    'Adaeze Okonkwo',
    '2026/2027 — 1st',
    'Test Academy',
    '₦157,500.50',
    'https://testacademy.example.com/parent/fees',
)
PAYMENT_EXAMPLE = (
    'Chinedu',
    'Adaeze Okonkwo',
    '2026/2027 — 1st',
    'Test Academy',
    '₦50,000.00',
    '₦157,500.50',
    'https://testacademy.example.com/parent/fees',
)
RESULT_EXAMPLE = (
    'Chinedu',
    'Adaeze Okonkwo',
    '2026/2027 — 1st',
    'Test Academy',
    'https://testacademy.example.com/parent/results',
)


class WhatsAppTemplateDraft:
    """One Utility template, plus the exact JSON body to submit."""

    def __init__(self, name, body, parameter_names, example):
        self.name = name
        self.language = TEMPLATE_LANGUAGE
        self.category = TEMPLATE_CATEGORY
        self.body = body
        self.footer = TEMPLATE_FOOTER
        self.parameter_names = parameter_names
        self.example = example

    def submission(self):
        """POST body for ``/{WABA_ID}/message_templates``."""
        return {
            'name': self.name,
            'language': self.language,
            'category': self.category,
            'components': [
                {
                    'type': 'BODY',
                    'text': self.body,
                    'example': {'body_text': [list(self.example)]},
                },
                {'type': 'FOOTER', 'text': self.footer},
            ],
        }

    def preview(self, parameters):
        """Body with {{n}} replaced. For the console backend and tests."""
        text = self.body
        for index, value in enumerate(parameters, start=1):
            text = text.replace('{{%d}}' % index, str(value))
        return text


INVOICE_TEMPLATE = WhatsAppTemplateDraft(
    INVOICE_TEMPLATE_NAME, INVOICE_BODY, INVOICE_PARAMETERS, INVOICE_EXAMPLE,
)
PAYMENT_TEMPLATE = WhatsAppTemplateDraft(
    PAYMENT_TEMPLATE_NAME, PAYMENT_BODY, PAYMENT_PARAMETERS, PAYMENT_EXAMPLE,
)
RESULT_TEMPLATE = WhatsAppTemplateDraft(
    RESULT_TEMPLATE_NAME, RESULT_BODY, RESULT_PARAMETERS, RESULT_EXAMPLE,
)

TEMPLATES = (INVOICE_TEMPLATE, PAYMENT_TEMPLATE, RESULT_TEMPLATE)


def draft_text():
    """Plain-text copy of the three templates, for Meta approval."""
    blocks = []
    for template in TEMPLATES:
        variables = '\n'.join(
            '  {{%d}} %s — example: %s' % (index, name, sample)
            for index, (name, sample) in enumerate(
                zip(template.parameter_names, template.example),
                start=1,
            )
        )
        blocks.append(
            'Name: %s\nLanguage: %s\nCategory: %s\nBody:\n%s\n'
            'Footer: %s\nVariables:\n%s' % (
                template.name,
                template.language,
                template.category,
                template.body,
                template.footer,
                variables,
            )
        )
    return '\n\n'.join(blocks)
