export default function handler(req, res) {
  const { code, state } = req.query;

  if (!code) {
    return res.status(400).send('Código não fornecido.');
  }

  const redirectUrl = `playrifa://oauth?code=${code}&state=${state || ''}`;
  res.redirect(302, redirectUrl);
}
