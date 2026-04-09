#include <KAbstractFileItemActionPlugin>
#include <KFileItemListProperties>
#include <KPluginFactory>
#include <QAction>
#include <QList>
#include <QProcess>
#include <QWidget>
#include <QKeySequence>

class QuickViewPlugin : public KAbstractFileItemActionPlugin
{
    Q_OBJECT
public:
    explicit QuickViewPlugin(QObject *parent, const QVariantList &)
        : KAbstractFileItemActionPlugin(parent)
    {}

    QList<QAction *> actions(const KFileItemListProperties &props, QWidget *parentWidget) override
    {
        if (props.urlList().isEmpty())
            return {};

        auto *action = new QAction(QIcon::fromTheme(QStringLiteral("view-preview")),
                                   QStringLiteral("Quick View"),
                                   parentWidget);
        action->setShortcut(QKeySequence(Qt::Key_Space));

        const auto urls = props.urlList();
        connect(action, &QAction::triggered, this, [urls]() {
            QStringList args;
            for (const auto &url : urls)
                args << url.toLocalFile();
            QProcess::startDetached(QStringLiteral("python3"),
                                    QStringList() << QStringLiteral("/home/lex/.local/bin/quickview") << args);
        });

        return {action};
    }
};

K_PLUGIN_CLASS_WITH_JSON(QuickViewPlugin, "quickviewplugin.json")

#include "quickviewplugin.moc"
