"""
PDF policy generator and FAISS vector store builder.

Generates 3 realistic policy PDFs (return, shipping, FAQ) and builds
a FAISS vector store from them.

Run standalone:  python vectorstore.py
"""
from fpdf import FPDF

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

from config import (
    POLICIES_DIR,
    VECTORSTORE_DIR,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    EMBEDDING_MODEL,
)


# ═══════════════════════════════════════════════════════════════════════
# PDF Generation
# ═══════════════════════════════════════════════════════════════════════

def _make_pdf(filename: str, title: str, sections: list[tuple[str, str]]) -> None:
    """Create a simple PDF with a title and multiple sections."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, title, ln=True, align="C")
    pdf.ln(8)

    for heading, body in sections:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 10, heading, ln=True)
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, body)
        pdf.ln(4)

    path = POLICIES_DIR / filename
    pdf.output(str(path))
    print(f"  📄 Generated {path.name}")


def generate_policy_pdfs() -> None:
    """Generate all policy PDFs."""
    print("Generating policy PDFs...")

    _make_pdf("return_policy.pdf", "Return & Refund Policy", [
        ("Overview",
         "We want you to be completely satisfied with your purchase. "
         "If you are not satisfied, you may return most items within 30 days "
         "of delivery for a full refund or exchange."),
        ("Eligibility",
         "Items must be unused, in original packaging, and accompanied by a receipt or proof of purchase. "
         "The following items are NOT eligible for return: "
         "gift cards, downloadable software, perishable goods, and personalized items."),
        ("Electronics Returns",
         "Electronics may be returned within 15 days of delivery. "
         "Items must include all original accessories, manuals, and packaging. "
         "A 10% restocking fee applies to opened electronics over $100."),
        ("Clothing Returns",
         "Clothing items may be returned within 30 days. "
         "Items must be unworn, unwashed, and have original tags attached. "
         "Undergarments and swimwear are final sale and cannot be returned."),
        ("Refund Process",
         "Once we receive your returned item, we will inspect it and notify you of the approval status. "
         "Approved refunds are processed within 5-7 business days to your original payment method. "
         "Shipping costs are non-refundable unless the return is due to our error."),
        ("Exchanges",
         "If you wish to exchange an item for a different size or color, "
         "please initiate a return and place a new order. "
         "We do not offer direct exchanges at this time."),
    ])

    _make_pdf("shipping_policy.pdf", "Shipping Policy", [
        ("Domestic Shipping",
         "Standard shipping (5-7 business days): FREE on orders over $50, otherwise $4.99. "
         "Expedited shipping (2-3 business days): $9.99. "
         "Overnight shipping (1 business day): $19.99. "
         "Orders placed before 2 PM EST on business days ship the same day."),
        ("International Shipping",
         "We ship to over 50 countries worldwide. "
         "International standard shipping (10-15 business days): $14.99. "
         "International express shipping (5-7 business days): $29.99. "
         "Customs duties and taxes are the responsibility of the recipient."),
        ("Order Tracking",
         "A tracking number is emailed within 24 hours of shipment. "
         "You can track your order on our website or directly through the carrier's website. "
         "If tracking shows 'delivered' but you haven't received the package, "
         "please contact us within 48 hours."),
        ("Shipping Restrictions",
         "Certain items (e.g., lithium batteries, aerosols) may have shipping restrictions. "
         "We do not ship to PO Boxes for expedited or overnight orders. "
         "Hazardous materials cannot be shipped internationally."),
    ])

    _make_pdf("faq.pdf", "Frequently Asked Questions", [
        ("How do I create an account?",
         "Visit our website and click 'Sign Up' in the top right corner. "
         "Enter your email, create a password, and fill in your profile details. "
         "You'll receive a confirmation email to verify your account."),
        ("Can I modify my order after placing it?",
         "Orders can be modified within 1 hour of placement. "
         "After that, the order enters processing and cannot be changed. "
         "Contact customer service immediately if you need to make changes."),
        ("What payment methods do you accept?",
         "We accept Visa, MasterCard, American Express, Discover, PayPal, UPI, "
         "and Cash on Delivery (for domestic orders only). "
         "All payments are processed through secure, encrypted connections."),
        ("Do you offer gift wrapping?",
         "Yes! Gift wrapping is available for $3.99 per item. "
         "You can add a personalized message of up to 150 characters. "
         "Select 'Gift Wrap' option during checkout."),
        ("How do I contact customer support?",
         "Email: support@shopexample.com (response within 24 hours). "
         "Phone: 1-800-555-0199 (Mon-Fri, 9 AM - 6 PM EST). "
         "Live Chat: Available on our website 24/7."),
        ("What is your price match guarantee?",
         "We will match the price of any identical item sold by a major retailer within 14 days of purchase. "
         "Contact support with proof of the lower price. "
         "Does not apply to marketplace sellers, clearance items, or coupon/promo-based prices."),
    ])

    print("✅ All policy PDFs generated!\n")


# ═══════════════════════════════════════════════════════════════════════
# Vector Store
# ═══════════════════════════════════════════════════════════════════════

def build_vectorstore() -> FAISS:
    """Load PDFs, chunk, embed, and build FAISS vector store."""
    # Generate PDFs if they don't exist
    pdf_files = list(POLICIES_DIR.glob("*.pdf"))
    if len(pdf_files) < 3:
        generate_policy_pdfs()
        pdf_files = list(POLICIES_DIR.glob("*.pdf"))

    # Load all PDFs
    print("Loading PDFs...")
    all_docs = []
    for pdf_path in sorted(pdf_files):
        loader = PyPDFLoader(str(pdf_path))
        docs = loader.load()
        for doc in docs:
            doc.metadata["source"] = pdf_path.name
        all_docs.extend(docs)
        print(f"  📄 Loaded {pdf_path.name} ({len(docs)} pages)")

    # Split into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(all_docs)
    print(f"  ✂️  Split into {len(chunks)} chunks")

    # Embed and store
    print("Building FAISS index...")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    vectorstore = FAISS.from_documents(chunks, embeddings)

    # Save to disk
    vectorstore.save_local(str(VECTORSTORE_DIR))
    print(f"✅ FAISS index saved to {VECTORSTORE_DIR}\n")

    return vectorstore


def load_vectorstore() -> FAISS:
    """Load existing FAISS vector store from disk, or build if missing."""
    if VECTORSTORE_DIR.exists():
        print("Loading existing FAISS index...")
        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        return FAISS.load_local(
            str(VECTORSTORE_DIR), embeddings, allow_dangerous_deserialization=True
        )
    return build_vectorstore()


if __name__ == "__main__":
    generate_policy_pdfs()
    build_vectorstore()
