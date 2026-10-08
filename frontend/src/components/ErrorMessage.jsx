// ErrorMessage — shows a friendly red error box.
// WHY a separate component? App.jsx, and potentially other components,
// may need to show errors. One component means one place to style it.

export default function ErrorMessage({ message }) {
  // If there is no message, render nothing at all.
  if (!message) return null

  return (
    // role="alert" tells screen readers to announce this immediately
    // when it appears, without the user having to focus on it.
    <div className="error-message" role="alert">
      <strong>Error: </strong>{message}
    </div>
  )
}
