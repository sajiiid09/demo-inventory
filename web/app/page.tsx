export default function Home() {
  return (
    <main className="mx-auto max-w-xl p-10">
      <h1 className="text-2xl font-semibold">MicroLoan Demo</h1>
      <p className="mt-2 text-gray-600">
        Skeleton is up. The app shell arrives with phase 8; until then the whole
        system is drivable from the API docs at{" "}
        <a className="underline" href="http://localhost:8000/docs">
          http://localhost:8000/docs
        </a>
        .
      </p>
    </main>
  );
}
