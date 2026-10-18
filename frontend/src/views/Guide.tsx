import { PageHeader } from '../components/ui'

export default function Guide() {
  return (
    <>
      <PageHeader title="Help" subtitle="The words and steps used in Ledgerly." />
      <div className="two-col">
        <section className="panel pad">
          <h2>Words you will see</h2>
          <dl>
            <dt>Credit (udhaar)</dt><dd>Goods or money given on credit. The customer owes more.</dd>
            <dt>Payment</dt><dd>Money received. The customer owes less.</dd>
            <dt>Balance</dt><dd>Credits minus payments. Crossed-out rows are not counted.</dd>
            <dt>Aging</dt><dd>How long unpaid credit has been waiting: 0–30, 31–60, 61+ days, or no date.</dd>
          </dl>
        </section>
        <section className="panel pad">
          <h2>Adding a khata page</h2>
          <ol className="steps">
            <li><strong>Photograph the page.</strong> Whole page, even light.</li>
            <li><strong>Check every card.</strong> Fix names, dates, amounts and credit vs payment. Mark crossed-out rows.</li>
            <li><strong>Pick the customer.</strong> Similar names are only suggestions; you decide whether to merge.</li>
            <li><strong>Confirm.</strong> Only then do entries change balances.</li>
          </ol>
        </section>
      </div>
      <section className="panel pad">
        <h2>Privacy</h2>
        <p>Ledgerly runs on this computer. Photos are read by a model served locally through Ollama, and records are stored in a local database. There is no account and no cloud service in the default setup.</p>
        <p className="muted">If you later connect a hosted API, your photos will leave this machine.</p>
      </section>
    </>
  )
}
